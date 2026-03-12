# Atlas 2.0 — Technical Architecture & Discovery Intelligence
> Deep reference documentation. Written from source. Not a summary.

---

## Table of Contents

1. [The RAG System](#1-the-rag-system)
   - 1.1 [Ingestion Pipeline](#11-ingestion-pipeline)
   - 1.2 [Hybrid Retrieval: The 8-Step Pipeline](#12-hybrid-retrieval-the-8-step-pipeline)
   - 1.3 [Reciprocal Rank Fusion (RRF)](#13-reciprocal-rank-fusion-rrf)
   - 1.4 [Graph Expansion](#14-graph-expansion)
   - 1.5 [Answer Generation](#15-answer-generation)
2. [The Discovery OS](#2-the-discovery-os)
   - 2.1 [Session Filesystem: The Shared Brain](#21-session-filesystem-the-shared-brain)
   - 2.2 [Session Memory: Two Formats, One Truth](#22-session-memory-two-formats-one-truth)
   - 2.3 [Phase 1: Coordinator — HITL Session Bootstrap](#23-phase-1-coordinator--hitl-session-bootstrap)
   - 2.4 [Phase 2: Executor — The ReAct Loop](#24-phase-2-executor--the-react-loop)
   - 2.5 [The Two-Model Architecture](#25-the-two-model-architecture)
   - 2.6 [The LLM-to-Deterministic Handoff](#26-the-llm-to-deterministic-handoff)
3. [How Discovery Actually Happens](#3-how-discovery-actually-happens)
   - 3.1 [Creating New Ideas](#31-creating-new-ideas)
   - 3.2 [Building On Ideas](#32-building-on-ideas)
   - 3.3 [Learning From Mistakes](#33-learning-from-mistakes)
   - 3.4 [Why This Is Real Discovery, Not Hallucination](#34-why-this-is-real-discovery-not-hallucination)
4. [LangGraph Internals: interrupt() and Command(resume=...)](#4-langgraph-internals-interrupt-and-commandresume)
5. [Database & Storage Layout](#5-database--storage-layout)

---

## 1. The RAG System

The RAG system is the knowledge substrate that all agents query. It is not a chatbot wrapper around a vector database. It is a 8-step hybrid pipeline that deliberately combines four independent retrieval strategies and fuses them.

### 1.1 Ingestion Pipeline

**File**: `src/backend/app/services/ingest.py`

When a document is uploaded, these steps run sequentially before any query can use it:

#### Step 1: Text Extraction
```
PDF  → pdfplumber (primary)
         → pypdf (fallback if pdfplumber raises)
DOCX → python-docx
Optional: Docling VLM parser for complex layouts (tables, multi-column figures)
```
The fallback chain is important: pdfplumber is more accurate for structured PDFs, pypdf is faster and handles corrupted files.

#### Step 2: Chunking — Fixed vs. Semantic
Two modes controlled by `settings.ENABLE_SEMANTIC_CHUNKING`:

**Fixed chunking** (default): 1000 tokens, configurable overlap. Every chunk is exactly the same size. Simple, predictable, but chunk boundaries cut across sentence and paragraph boundaries.

**Semantic chunking**: Splits text into sentences, computes embeddings for each sentence, and identifies cut-points where cosine similarity between adjacent sentences drops below a threshold. This keeps semantically coherent content together. A paragraph about IC50 values doesn't get split halfway through just because you hit 1000 tokens.

#### Step 3: RAPTOR Hierarchical Summarization (optional)
If enabled, after chunking:
1. Cluster leaf chunks by semantic similarity (k-means over embeddings)
2. LLM generates a summary of each cluster → these become "parent" chunks
3. Repeat up the tree until one root summary exists

This enables retrieval at multiple granularities: detailed exact text at the leaf level, high-level summaries at higher levels.

#### Step 4: Embedding & Qdrant Storage
Each chunk is embedded with `nomic-embed-text-v1.5` (768-dimensional vectors) via sentence-transformers. The embedding runs on CPU or CUDA depending on the machine.

Each point stored in Qdrant has:
```json
{
  "id": "uuid",
  "vector": [float × 768],
  "payload": {
    "text": "raw chunk text",
    "doc_id": "uuid",
    "metadata": {
      "filename": "paper.pdf",
      "page": 3,
      "chunk_index": 12
    }
  }
}
```

Simultaneously, the chunk is written to the `document_chunks` SQLite table.

#### Step 5: Entity Extraction → Knowledge Graph
GLiNER (`gliner_small-v2.1`) runs Named Entity Recognition over each chunk. GLiNER is a zero-shot NER model — it doesn't need domain-specific training to identify chemical compounds, proteins, targets, etc. It generalizes.

For each entity extracted:
- A `Node` row is inserted into SQLite: `(id, label, name, description, chunk_id, properties JSON)`
- Edges are created between entities that co-occur in the same chunk: `(source_id, target_id, type=CO_OCCURS)`

This builds the knowledge graph incrementally as documents are ingested.

#### Step 6: BM25 Indexing
All chunk texts are loaded into an in-memory `bm25s` index. BM25 (Best Match 25) is a probabilistic keyword scoring function. It scores chunks by term frequency, inverse document frequency, and document length normalization. This is the classic information retrieval algorithm — it finds exact keyword matches that dense vectors often miss.

---

### 1.2 Hybrid Retrieval: The 8-Step Pipeline

**File**: `src/backend/app/services/retrieval.py` — `query_atlas()`

Every query to the system runs through all 8 steps:

#### Step 0: Query Entity Extraction
```python
async def _extract_query_entities(self, query: str) -> Dict[str, Any]:
```
Before any search, the LLM is called with a structured prompt to extract:
- `entities`: named entities in the query ("KINASE-X", "aspirin")
- `dates`: temporal references ("1920", "Q3 2023")
- `date_ranges`: ranges ("1920–1930")
- `key_phrases`: exact phrases that should be substring-matched

This is cheap (low temperature, max 512 tokens, ~100ms). It enriches the query from "find papers about compound X" into a structured signal that drives multiple downstream search strategies.

#### Step 0.5: Active Document Scoping
```python
doc_query = session.query(Document).filter(Document.status == "completed")
if project_id:
    doc_query = doc_query.filter(Document.project_id == project_id)
```
Only chunks from completed, in-scope documents are considered. This scopes the retrieval to the current project's corpus, preventing cross-contamination between projects.

#### Step 1: Vector Search (Semantic)
```python
query_embedding = await self._embed_text(user_question)
vector_results = self.qdrant_client.query_points(
    collection_name=self.collection_name,
    query=query_embedding,
    limit=20,
).points
```
Returns top 20 nearest neighbors by cosine similarity in the 768-d embedding space. These are semantically related to the query even if they share no keywords. "Inhibitor of tyrosine kinase" will surface results that contain "kinase blocker" or "phosphorylation antagonist".

Results are filtered to `active_doc_ids` immediately after the search.

#### Step 2: Entity-Based Matching
```python
matching_nodes = node_query.filter(
    func.lower(
        func.json_extract(Node.properties, '$.name')
    ).contains(entity_name.lower())
).limit(20).all()
```
For each entity extracted from the query, SQLite JSON functions (`json_extract`) do a case-insensitive substring match against node names in the knowledge graph. For each matched node, the associated chunk is retrieved from Qdrant by chunk_id. These chunks get a `relevance_score = 0.95` (high confidence, explicit entity match).

#### Step 3: Exact Text Matching
For dates and key phrases, the system scrolls through Qdrant payloads (not by vector, but by full text scan) and checks `if term.lower() in text`. These matches get `relevance_score = 0.98` — the highest baseline, because an exact term match is definitionally relevant.

#### Step 3.5: BM25 Sparse Search
```python
bm25_results = self.bm25_service.search(
    query=user_question,
    top_k=20,
    doc_ids=active_doc_ids,
)
```
BM25 ranks chunks by keyword overlap with the query, weighted by IDF (rare words matter more than common ones). This catches technical jargon, chemical names, and abbreviations that dense vectors sometimes blur together.

#### Step 4: Reciprocal Rank Fusion
All four result lists are passed to `rrf_fuse()`. See section 1.3 below for the mathematics.

#### Step 4.5: FlashRank Cross-Encoder Reranking
```python
vector_chunks = await self.reranker.rerank(
    query=user_question,
    documents=candidate_chunks,
    top_n=settings.RERANK_TOP_N,
)
```
After RRF produces a fused ranked list of ~20 candidates, FlashRank runs a cross-encoder over each (query, chunk) pair. A cross-encoder reads both the query and the document together (unlike bi-encoders that embed them separately), so it can model fine-grained relevance signals like "this chunk answers the exact question asked" vs. "this chunk is about the same topic but doesn't answer the question."

`RERANK_TOP_N` defaults to 5. This is the final answer set.

#### Step 5: Graph Expansion
See section 1.4 below.

---

### 1.3 Reciprocal Rank Fusion (RRF)

**File**: `src/backend/app/services/bm25_index.py` — `rrf_fuse()`

RRF is the mathematical core that makes hybrid retrieval work. Given N ranked lists of documents, RRF assigns each document a combined score:

```
RRF_score(doc) = Σ_i  1 / (k + rank_i)
```

Where:
- `k = 60` (a smoothing constant that prevents top-ranked documents from dominating)
- `rank_i` is the document's rank in list i (1-indexed)
- The sum is over all lists where the document appears

A document that appears as:
- Rank 1 in vector search → contributes `1/(60+1) = 0.0164`
- Rank 3 in BM25 → contributes `1/(60+3) = 0.0159`
- Rank 2 in entity matching → contributes `1/(60+2) = 0.0161`

Combined: `0.0484`

A document that is Rank 1 in only one list: `0.0164`

RRF rewards consistency across retrieval strategies over dominance in a single one. A chunk that is "pretty good" in all four strategies beats a chunk that is "perfect" in vector search but absent from the others.

---

### 1.4 Graph Expansion

After the top-5 reranked chunks are determined, the system finds all knowledge graph nodes associated with those chunks (by `chunk_id` pointer in `node.properties`), then loads all edges connected to those nodes and all nodes at the other end of those edges:

```python
# Load matched nodes + their edges + connected nodes
nodes = session.query(Node).options(
    joinedload(Node.outgoing_edges).joinedload(Edge.target_node),
    joinedload(Node.incoming_edges).joinedload(Edge.source_node),
).filter(Node.id.in_(node_id_list)).all()

edges = session.query(Edge).filter(
    or_(Edge.source_id.in_(node_id_list), Edge.target_id.in_(node_id_list))
).all()
```

`joinedload()` prevents the N+1 query problem. This is one SQL query per node set, not one per node.

The output is a 1-hop subgraph: the set of all nodes directly connected to the retrieved chunks' entities. This adds relational context that pure text retrieval cannot. If you retrieved a chunk about "compound X", graph expansion also returns that `compound X → CAUSES → hepatotoxicity` edge even if the hepatotoxicity chunk wasn't in the top 5.

---

### 1.5 Answer Generation

The final LLM call has temperature `0.1` (near-deterministic) and a strict system prompt:

```python
system_msg = (
    "You are a precise research librarian. Answer the user's question based primarily "
    "on the provided context. If you cannot find the answer, say "
    "\"I cannot find this information in the available documents.\""
)
```

The context string includes labeled chunks with scores and source citations, plus graph nodes and edges in plain text. The user message has mandatory citation instructions: every fact must cite `[Source: filename.pdf, Page: X]`. The LLM is not being asked to reason from its weights — it is being asked to read a curated document set and cite it accurately.

---

## 2. The Discovery OS

The Discovery OS is the multi-agent research system that runs on top of RAG. It is architecturally separate from the chat interface. Its defining property: **agents do not generate answers, they generate Python scripts that compute answers.**

---

### 2.1 Session Filesystem: The Shared Brain

**File**: `src/backend/app/services/discovery_session.py` — `initialize_session()`

When a session is created:

```python
base_path = Path(settings.DATA_DIR) / "discovery" / session_id
base_path.mkdir(parents=True, exist_ok=True)

generated_path = base_path / "generated"
generated_path.mkdir(exist_ok=True)

jobs_file = base_path / "jobs.json"
jobs_file.write_text(json.dumps({}))
```

The full session directory:

```
data/discovery/{session_id}/
├── jobs.json                  ← Job queue (empty at init, future use)
├── session_memory.json        ← Machine-readable state (Pydantic model serialized)
├── SESSION_INIT.md            ← Human-readable initialization report (written by Coordinator)
└── generated/                 ← All Executor outputs
    ├── execution_log.txt       ← Cumulative log of all script runs (appended per iteration)
    ├── generate_candidates.py  ← LLM-authored script (iteration 1)
    ├── candidates.csv          ← Output of iteration 1
    ├── screen_candidates.py    ← LLM-authored script (iteration 2)
    ├── hits.csv                ← Output of iteration 2
    └── ...
```

This filesystem is the **single source of truth** for the session. Agents do not pass state through function arguments or in-memory dicts across calls — they read from and write to this directory.

---

### 2.2 Session Memory: Two Formats, One Truth

**File**: `src/backend/app/services/discovery_session.py` — `SessionMemoryService`

The memory is always written in two formats simultaneously:

```python
@staticmethod
def save_session_memory(session_id: str, memory_data: SessionMemoryData) -> None:
    # 1. Machine-readable JSON
    json_path = SessionMemoryService._get_memory_json_path(session_id)
    json_path.write_text(memory_data.model_dump_json(indent=2), encoding="utf-8")

    # 2. Human-readable Markdown
    md_path = SessionMemoryService._get_init_md_path(session_id)
    md_content = SessionMemoryService._generate_markdown_report(memory_data)
    md_path.write_text(md_content, encoding="utf-8")
```

**`session_memory.json`** is what the Executor reads at the start of every invocation:
```python
session_memory = SessionMemoryService.load_session_memory(session_id)
extracted_goals = session_memory.research_goals
```

The full `SessionMemoryData` Pydantic model:
```python
class SessionMemoryData(BaseModel):
    session_id: str
    initialized_at: str
    domain: Optional[str] = None           # "organic_chemistry" | "materials_science" | ...
    corpus_context: Optional[CorpusContext] = None  # entities, document_ids, summary
    research_goals: List[str]              # The definitive goal list from Coordinator
    constraints: Dict[str, Any]            # Property constraints (MW, LogP, etc.)
    agents_completed: List[str]            # ["coordinator", "executor_iteration_1", ...]
    current_stage: str                     # "initializing" | "coordinator_complete" | ...
    metadata: Dict[str, Any]               # project_id, coordinator_turns, etc.
```

**`SESSION_INIT.md`** is generated by `_generate_markdown_report()`. It is a structured Markdown document that a human can read to understand exactly what was decided during initialization. It is not used by agent code — it exists for the researcher to inspect and for future agents that read the filesystem directly.

The `.md` file format was chosen deliberately over raw JSON for two reasons:
1. **Human readability**: The researcher can open it in any editor and understand the session state.
2. **Future LLM consumption**: If a new agent is added that reads session context, Markdown is far more parseable by LLMs than raw JSON dicts. The structure (`## Research Goals`, `## Constraints`) maps cleanly to LLM prompts.

---

### 2.3 Phase 1: Coordinator — HITL Session Bootstrap

**File**: `src/backend/app/services/agents/coordinator.py`

The Coordinator runs once per session. Its job is to transform a researcher's vague intent into a precise, machine-readable `research_goals` list that every subsequent agent can execute against.

#### State Machine

```python
class CoordinatorState(TypedDict, total=False):
    messages: List[Dict[str, Any]]      # Conversation history (last 10 kept)
    extracted_goals: List[str]          # Accumulated goals (append-only)
    missing_context: List[str]          # What's still unknown
    corpus_summary: str                 # RAG scan result
    corpus_entities: List[str]          # Entities from knowledge graph
    status: str                         # "scanning" | "questioning" | "complete"
    turn_count: int
    max_turns: int                      # Hard limit: 5
    project_id: str
    session_id: str
```

#### LangGraph Definition

```python
sg = StateGraph(CoordinatorState)
sg.add_node("scan_corpus", scan_corpus)
sg.add_node("analyze_and_ask", analyze_and_ask)

sg.set_entry_point("scan_corpus")
sg.add_edge("scan_corpus", "analyze_and_ask")
sg.add_conditional_edges("analyze_and_ask", should_continue, {
    "ask": "analyze_and_ask",   # loop: not ready yet
    "end": END,                  # complete: goals are defined
})
```

#### Node 1: `scan_corpus`
Queries RAG with a broad summarization prompt:
```python
query = (
    "Summarize the key topics, molecules, biological targets, "
    "methodologies, and findings in this research corpus."
)
result = await retrieval_service.query_atlas(user_question=query, project_id=project_id)
```
This runs the full 8-step hybrid retrieval pipeline. The returned `vector_chunks[:8]` (first 300 chars each) become the `corpus_summary`. The returned `graph_nodes[:20]` labels become `corpus_entities`. This gives the Coordinator ground truth about what the researcher has already uploaded.

#### Node 2: `analyze_and_ask`
The LLM (MiniMax, temperature 0.3, max 512 tokens) is given:
- The corpus summary and entities (what you have uploaded)
- The accumulated goals so far (what has been confirmed)
- The last 10 conversation turns (context)
- A checklist of what it needs to collect: domain, objective, property constraints, exclusion criteria, success metrics

It must return this JSON schema (enforced via `response_format=json_object`):
```python
COORDINATOR_ANALYSIS_SCHEMA = {
    "assessment": str,              # brief evaluation of current state
    "new_goals_extracted": [str],   # goals extracted from latest user message
    "still_missing": [str],         # what is still unknown
    "ready_to_proceed": bool,       # True = enough info to start execution
    "question": str,                # the next question for the researcher
    "options": [str],               # 2–4 multiple-choice options + "Other..."
}
```

New goals are merged into `extracted_goals` (deduplication: `if g not in goals`). If `ready_to_proceed=True` or `turn_count >= max_turns - 1`, the state is set to `"complete"` and the loop exits.

Otherwise, the graph **pauses** at:
```python
user_response = interrupt(question_payload)
```

This is LangGraph's HITL mechanism. The graph serializes its full state to `MemorySaver` (SQLite-backed), the async generator returns, and the API endpoint sends an SSE event of type `coordinator_question` to the frontend. The frontend renders the question and options.

When the researcher answers, the frontend POSTs to `/api/discovery/{session_id}/coordinator/chat` with the answer as `message`. The route handler detects `snapshot.next` is non-empty (graph is paused), constructs `Command(resume=user_message)`, and calls `compiled.astream(Command(resume=...), ...)`. The graph resumes at the line after `interrupt()`, with `user_response = the_answer_string`.

#### Finalization: `_finalize_coordinator()`

When the loop exits, this function:
1. Calls `DiscoverySessionService.update_coordinator_goals(session_id, goals)` → writes goals to `DiscoverySession.target_params["coordinator_extracted_goals"]` in SQLite
2. Calls `SessionMemoryService.save_session_memory(session_id, memory_data)` → writes `session_memory.json` + `SESSION_INIT.md`
3. Domain is inferred by keyword matching on goals text: chemistry keywords → `"organic_chemistry"`, material keywords → `"materials_science"`, etc.
4. Emits `coordinator_complete` SSE event with the full goal list

---

### 2.4 Phase 2: Executor — The ReAct Loop

**File**: `src/backend/app/services/agents/executor.py`

The Executor runs after the Coordinator. It reads the session memory, plans tasks, writes Python scripts, executes them, and loops until goals are satisfied.

#### State Machine

```python
class ExecutorState(TypedDict, total=False):
    session_id: str
    project_id: str
    extracted_goals: List[str]        # from session_memory.json
    current_task: str                  # what to do this iteration
    generated_script: str             # the Python script text
    script_filename: str
    script_description: str
    required_packages: List[str]
    script_status: str                # "draft" | "approved" | "rejected" | "executed"
    execution_output: str             # subprocess stdout
    execution_error: Optional[str]    # subprocess stderr or None
    artifacts_generated: List[str]   # all files in generated/
    iteration: int
    max_iterations: int               # hard limit: 10
    status: str                       # "planning" | "scripting" | "awaiting_approval" | "executing" | "complete"
    auto_approve: bool
```

#### LangGraph Definition

```python
sg = StateGraph(ExecutorState)
sg.add_node("plan_task", plan_task)
sg.add_node("generate_script", generate_script)
sg.add_node("await_approval", await_approval)
sg.add_node("execute_script", execute_script)

sg.set_entry_point("plan_task")
sg.add_edge("plan_task", "generate_script")

sg.add_conditional_edges("generate_script", should_await_approval, {
    "await": "await_approval",    # HITL: show script to researcher
    "execute": "execute_script",  # auto_approve=True: skip
})

sg.add_edge("await_approval", "execute_script")

sg.add_conditional_edges("execute_script", should_continue, {
    "continue": "plan_task",     # loop back for next iteration
    "end": END,                   # complete or max_iterations reached
})
```

#### Node 1: `plan_task`

Reads the filesystem — specifically `generated_folder.iterdir()` to list all existing artifacts:
```python
existing_files = [f.name for f in generated_folder.iterdir() if f.is_file()]
existing_summary = ", ".join(existing_files) if existing_files else "None yet"
```

LLM prompt (MiniMax, temperature 0.3, max 512 tokens):
```
=== RESEARCH GOALS ===
- Find KINASE-X inhibitors with IC50 < 1μM
- Apply Lipinski filter: MW < 500, LogP 2-5

=== EXISTING ARTIFACTS ===
candidates.csv, execution_log.txt

=== CURRENT ITERATION ===
Iteration 2

Analyze the goals and existing artifacts. Determine the next logical task.
```

Output schema: `{"assessment": str, "next_task": str, "reasoning": str}`

If `next_task == "complete"`, the graph exits. Otherwise, the task description is passed to `generate_script`.

#### Node 2: `generate_script`

LLM prompt (MiniMax, temperature 0.4, max 2048 tokens) includes the task, goals, existing artifacts, and an explicit template:
```python
"""Generate a complete, executable Python script that:
1. Uses deterministic tools (RDKit, NumPy, Pandas — NO LLM calls, NO external APIs that require auth)
2. Saves all outputs to the current directory (logs.txt, results.csv, plots.png)
3. Includes error handling and progress logging to stdout
4. Is fully self-contained (no external file dependencies except RDKit data)
5. Writes structured output (CSV or JSON) for machine readability

Available packages: rdkit, pandas, numpy, matplotlib, pathlib, csv, json"""
```

Output schema: `{"script_code": str, "filename": str, "description": str, "required_packages": [str]}`

After LLM output is parsed, the script is **immediately written to disk**:
```python
with open(script_path, "w", encoding="utf-8") as f:
    f.write(script_code)
```

The script exists on disk before it is executed. The researcher can see it, edit it, reject it.

#### Node 3: `await_approval` (HITL)

If `auto_approve=False`:
```python
approval_payload = {
    "script_code": script_code,
    "filename": filename,
    "description": description,
    "required_packages": packages,
}
user_decision = interrupt(approval_payload)
```

The graph pauses, SSE event `executor_awaiting_approval` fires. The frontend shows the script. The researcher can:
- **Approve**: `Command(resume="approved")` → `script_status = "approved"`, proceed to execute
- **Reject**: `Command(resume="reject")` → `script_status = "rejected"`, status = "complete" (stop)
- **Edit**: `Command(resume="edit:<new_code>")` → edited code is written to disk, `script_status = "approved"`, proceed to execute

#### Node 4: `execute_script`

```python
result = subprocess.run(
    [sys.executable, str(script_path)],
    cwd=str(generated_folder),         # CWD = generated/ so relative paths work
    capture_output=True,
    text=True,
    timeout=300,                        # 5-minute hard kill
    env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent)},
)
```

Execution is via `subprocess.run()` with the system Python interpreter. The PYTHONPATH is set so the script can import backend modules if needed, but the script prompt explicitly says to use only RDKit/pandas/numpy.

All stdout + stderr is appended to `execution_log.txt` with a separator:
```
============================================================
Script: screen_candidates.py (Iteration 2)
============================================================
STDOUT:
Starting screening of 200 candidates...
Applied MW filter: 147 remaining
Applied LogP filter: 89 remaining
Saved 89 hits to hits.csv
STDERR:
(none)
Exit Code: 0
```

After execution, the entire `generated/` directory is listed again:
```python
artifacts = [f.name for f in generated_folder.iterdir() if f.is_file()]
```

This becomes `artifacts_generated` in state, which `plan_task` reads next iteration to understand what has been produced.

On exit code != 0, `status = "complete"` — the loop stops. The error is in `execution_log.txt` and in the `execution_error` state field. (Future improvement: loop back to `plan_task` with the error as context so the LLM can fix the script.)

---

### 2.5 The Two-Model Architecture

**File**: `src/backend/app/services/discovery_llm.py`

The Discovery OS is entirely isolated from the global `LLMService` (which serves the chat interface). It uses its own `DiscoveryLLMService` with two separate API clients:

| Role | Model | Provider | Temperature | Use |
|---|---|---|---|---|
| Orchestration | `deepseek-reasoner` | DeepSeek API | 0.3 | Planning, analysis, assessment |
| Tool / Constrained | `MiniMax-M2.5` | MiniMax API | 0.3–0.4 | JSON schema generation, code writing |

Both use OpenAI-compatible API clients. LiteLLM is used for provider abstraction.

**Why two models?**

The planner needs to reason about goals, artifacts, and what to do next. DeepSeek R1 / deepseek-reasoner has strong chain-of-thought reasoning with its `<think>` tokens. It produces verbose, reflective output.

The code generator needs to produce syntactically valid, schema-conforming JSON with a `script_code` field that contains executable Python. MiniMax M2.5 is fast and reliable at structured generation. Its verbose reasoning would pollute the JSON output.

Forcing the same model to do both tasks creates a conflict: either the reasoning is truncated (bad plans) or the output format breaks (bad scripts).

**Constrained generation** (`generate_constrained()`):
```python
response = await client.chat.completions.create(
    model=self._tool_model,
    messages=[...],
    response_format={"type": "json_object"},
    temperature=temperature,
    max_tokens=max_tokens,
)
content = response.choices[0].message.content
return self._extract_json_from_content(content)
```

`_extract_json_from_content()` handles:
1. Clean JSON: `json.loads(content)` directly
2. Markdown-wrapped: strip ` ```json ... ``` ` fences and retry
3. Mixed content: find first `{` and last `}`, extract substring, retry

---

### 2.6 The LLM-to-Deterministic Handoff

This is the most important architectural decision in the system. The handoff happens at script execution.

The LLM (MiniMax) writes code like this (from the prompt template in `executor.py`):
```python
import sys
from pathlib import Path
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors

def main():
    print("Starting screening...")
    df = pd.read_csv("candidates.csv")

    # Deterministic RDKit property calculations
    def compute_props(smiles):
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None, None, None
        return (
            Descriptors.MolWt(mol),
            Descriptors.MolLogP(mol),
            Descriptors.TPSA(mol),
        )

    df[['MW', 'LogP', 'TPSA']] = df['smiles'].apply(
        lambda s: pd.Series(compute_props(s))
    )
    df_filtered = df[(df['MW'] < 500) & (df['LogP'].between(2, 5))]
    df_filtered.to_csv("hits.csv", index=False)
    print(f"Saved {len(df_filtered)} hits to hits.csv")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
```

When `execute_script` calls `subprocess.run([sys.executable, script_path], ...)`:
- The LLM's role is over. It wrote the code.
- The OS spawns a Python subprocess.
- `Descriptors.MolWt()` is a pure function in the RDKit library. It computes molecular weight from a molecular graph. It always returns the same number for the same SMILES string.
- There is no probability, no sampling, no hallucination at execution time.
- The CSV it writes contains exact numbers computed by deterministic algorithms.

The LLM's job was **code authorship**. The OS's job is **code execution**. These are completely separate.

---

## 3. How Discovery Actually Happens

The question is: is this genuine discovery, or is this a pipeline that generates plausible-looking results? The answer depends on understanding exactly where intelligence is being applied and what the artifacts mean.

### 3.1 Creating New Ideas

New ideas in Atlas 2.0 come from the intersection of two sources: the corpus (what is already known) and the LLM's generalization ability (what is plausible given what is known).

**The candidate generation step is where new ideas enter:**

The Executor's `plan_task` node, on a fresh session with no existing artifacts, will plan a task like: "Generate candidate SMILES from corpus context."

The `generate_script` node will write a Python script that:
1. Calls `retrieval_service.query_atlas("molecules discussed in corpus")` to retrieve known compounds
2. Constructs a structured prompt listing those compounds with their known properties
3. Calls the LLM to propose structurally related novel SMILES

The LLM generating novel SMILES is doing genuine chemical reasoning:
- It knows the pharmacophore of the known active compounds (from the corpus)
- It knows Lipinski rules (from training)
- It proposes analogues that preserve the pharmacophore but vary substituents

This is analogous to what a medicinal chemist does mentally — "if compound A has activity and LogP=4, maybe compound A' with a fluorine substitution at position 3 will have better membrane permeability." The LLM has seen thousands of SAR (Structure-Activity Relationship) papers and can apply this reasoning.

**The critical constraint:** the ideas are constrained by the corpus. The Coordinator's RAG scan surfaces what targets, methodologies, and known compounds the researcher has already established. The LLM proposes novelty within a bounded solution space, not arbitrary hallucination.

### 3.2 Building On Ideas

Building on ideas requires that later iterations have access to earlier results. This is implemented through the artifact filesystem.

In `plan_task`, the first thing the LLM sees is:
```
=== EXISTING ARTIFACTS ===
candidates.csv, hits.csv, execution_log.txt
```

The LLM knows `hits.csv` exists. It can plan the next task: "Perform PAINS filtering on hits.csv to remove reactive compounds."

The generated script for that task will:
```python
df = pd.read_csv("hits.csv")  # reads the output of the previous iteration
```

This is iterative refinement. Each iteration's output becomes the next iteration's input. The artifact list is the memory of what has been done. The goals list is the memory of where we are going.

A deeper form of building on ideas: the `execution_log.txt` accumulates all stdout from all scripts. If a future agent (or the researcher) reads this log, they can see not just what was produced but the intermediate print statements — "Applied MW filter: 147 remaining", "Applied LogP filter: 89 remaining" — which tell the story of why 200 candidates became 12 hits.

### 3.3 Learning From Mistakes

This is the most honest part of the architecture to examine. Currently, the system has partial learning-from-mistakes capability and one significant gap.

**What is implemented:**

The `execution_log.txt` captures every script's stdout and stderr, labeled by filename and iteration number. This is an audit trail of failures. If `screen_candidates.py` in iteration 2 crashes with `AttributeError: 'NoneType' has no attribute 'HasSubstructMatch'`, that error is in `execution_log.txt`.

The Executor's `plan_task` node reads `existing_files` — which now includes `execution_log.txt`. If the LLM is sophisticated enough, it can read the log and plan a corrected approach. The prompt is:
```
=== EXISTING ARTIFACTS ===
candidates.csv, execution_log.txt, screen_candidates.py
```

A strong reasoning model (DeepSeek) can infer from the presence of `execution_log.txt` and the absence of `hits.csv` that the screening step failed. It can plan: "Fix SMILES validation — add `if mol is None: continue` before calling HasSubstructMatch."

**What is partially implemented:**

When a script exits with code != 0, the current router does:
```python
if result.returncode != 0:
    return {
        "execution_error": result.stderr or "Script failed with non-zero exit code",
        "status": "complete",  # Stop on error
    }
```

This stops the loop. The system does not automatically retry. The researcher sees the `error` SSE event and must restart the Executor. This is intentional (safe-by-default) but means automatic recovery is not yet implemented.

**What is planned (documented in `executor.py` source comment):**

The comment `# Stop on error (or could retry with plan_task)` explicitly notes the planned improvement: when `returncode != 0`, instead of `status = "complete"`, set `status = "planning"` and include the `execution_error` in the state. The next `plan_task` call would see the error and plan a fix. This closes the automatic learning-from-mistakes loop.

**What the researcher can do now:**

The `await_approval` node supports `"edit:<new_code>"` as a resume value. If the researcher sees the generated script has a bug before it runs, they can edit it inline. The edited code is written back to disk and executed. This is human-directed learning — the researcher corrects the agent's mistake.

Additionally, the bioassay feedback system (`src/backend/app/services/domain_tools.py` — `create_or_update_feedback_node()`) writes wet-lab results back to the knowledge graph as new nodes. This closes the experimental loop: a compound is generated in silico, synthesized in the lab, tested, and the test result becomes a new knowledge graph node. Future RAG queries that retrieve that compound's node will also retrieve the experimental result edge. The system literally learns from experimental feedback.

### 3.4 Why This Is Real Discovery, Not Hallucination

The key architectural choices that prevent this from being a hallucination machine:

**1. Claims are grounded in the corpus, not in the LLM's weights alone.**
The Coordinator runs `query_atlas()` before any goal is set. The goals are shaped by what the corpus actually contains — not by what the LLM thinks is interesting about a topic.

**2. Numerical properties are computed, not generated.**
MW = 287.4 Da is computed by `Descriptors.MolWt(mol)` from a molecular graph. The LLM does not output property values. It outputs SMILES strings. The numbers are computed from those strings by RDKit.

**3. Filtering is rule-based, not probabilistic.**
"MW < 500" is a deterministic inequality check. Either `287.4 < 500` is True or it isn't. There is no probability of a false pass.

**4. The artifact trail is verifiable.**
Every script is saved. Every execution log is saved. Every output CSV is saved. The researcher can open `screen_candidates.py`, read it, verify the logic is correct, run it themselves, and get the same result. This is reproducible science.

**5. HITL keeps the researcher in the loop.**
The Coordinator's interrupt loop means the researcher explicitly confirms every goal before execution begins. The Executor's approval interrupt means the researcher sees every script before it runs. The system does not make autonomous decisions about what to do or how to do it without researcher sign-off.

The system's relationship to "discovery" is best described as: **it is a research automation layer that executes the scientific method more systematically than a human working alone.** It doesn't discover things the corpus cannot support. But it can rapidly traverse the solution space of candidates, apply property filters that would take a human days, surface graph-connected knowledge the researcher didn't think to look for, and produce a reproducible, auditable artifact trail of the entire process.

---

## 4. LangGraph Internals: `interrupt()` and `Command(resume=...)`

Both Coordinator and Executor use LangGraph's HITL primitives. Understanding how they work is necessary to understand how the system's conversational turns and approval flows are implemented.

### How `interrupt()` works

`interrupt(value)` is a LangGraph function that:
1. Raises an internal exception (`GraphInterrupt`) that LangGraph catches
2. Serializes the full graph state to the `MemorySaver` checkpointer (backed by SQLite in-memory)
3. Stores the interrupt payload (`value`) in the checkpoint under the current task's interrupts list
4. Returns control to the streaming loop — `astream()` generator raises `StopAsyncIteration`

The FastAPI route handler's `async for event in compiled.astream(...)` loop exits naturally. The SSE generator sends the interrupt payload as an event and then ends.

### How `Command(resume=...)` works

On the next HTTP request with the same `thread_id`:
```python
snapshot = await compiled.aget_state(config)
is_resume = bool(user_message and snapshot.next)
```

`snapshot.next` is non-empty when the graph is paused. The route handler calls:
```python
input_value = Command(resume=user_message)
async for event in compiled.astream(input_value, config=config, stream_mode="updates"):
```

LangGraph loads the checkpoint, finds the interrupted node, and re-executes it from the line after `interrupt()`. The return value of `interrupt()` is the `resume` value:
```python
user_response = interrupt(question_payload)
# user_response is now the string the researcher sent
```

### Thread ID Isolation

```python
thread_id = f"coordinator-{session_id}"  # Coordinator
thread_id = f"executor-{session_id}"     # Executor
```

Different prefixes prevent checkpoint collision between the two graphs for the same session.

---

## 5. Database & Storage Layout

### SQLite (`atlas.db`)

| Table | Key Columns | Purpose |
|---|---|---|
| `projects` | id, name, description | Workspace scoping |
| `documents` | id, project_id, filename, status, file_hash | Upload tracking |
| `document_chunks` | id, document_id, text, page, chunk_index | Raw chunk storage |
| `nodes` | id, label, name, description, chunk_id, properties (JSON) | Knowledge graph entities |
| `edges` | id, source_id, target_id, type, properties (JSON) | Relationships between entities |
| `discovery_sessions` | id, target_params (JSON), created_at, updated_at | Session metadata |

Indexes: `idx_nodes_label`, `idx_edges_source_target`, `idx_documents_file_hash`, `idx_chunk_document`

Foreign keys: `PRAGMA foreign_keys=ON`
WAL mode: enabled (allows concurrent reads during writes)

### Qdrant (`qdrant_storage/`)

Embedded mode — Qdrant runs in-process, no separate server. One collection per deployment (configured in `settings.QDRANT_COLLECTION`).

Each point: `{id: uuid, vector: float[768], payload: {text, doc_id, metadata}}`

### Session Filesystem (`data/discovery/`)

```
data/
└── discovery/
    └── {session_id}/
        ├── jobs.json
        ├── session_memory.json      ← Written by Coordinator, read by Executor
        ├── SESSION_INIT.md          ← Written by Coordinator, human-readable
        └── generated/
            ├── execution_log.txt    ← Appended every script run
            ├── *.py                 ← LLM-authored scripts (preserved)
            ├── *.csv                ← Computed results
            └── *.png                ← Plots (if script generates them)
```

---

*Last updated: 2026-03-11. Written from source: coordinator.py, executor.py, retrieval.py, discovery_session.py, ingest.py.*
