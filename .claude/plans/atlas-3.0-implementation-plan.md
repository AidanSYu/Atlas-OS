# Atlas 3.0 Implementation Plan - Front to Back Rebuild

**Version**: 1.0
**Date**: 2026-02-19
**Author**: Claude (Architect), commissioned by Antigravity plan
**Target**: Duke University Pilot (Alpha)

---

## Table of Contents

1. [Current State Assessment](#1-current-state-assessment)
2. [Architecture Overview](#2-architecture-overview)
3. [Phase 0: Foundation Fixes (Pre-Pilot Critical)](#3-phase-0-foundation-fixes)
4. [Phase 1: MoE Multi-Agent Backend](#4-phase-1-moe-multi-agent-backend)
5. [Phase 2: Streaming & Real-Time UX](#5-phase-2-streaming--real-time-ux)
6. [Phase 3: Research OS Frontend](#6-phase-3-research-os-frontend)
7. [Phase 4: Smart Reading & Context Engine](#7-phase-4-smart-reading--context-engine)
8. [Phase 5: Export & Integration Pipeline](#8-phase-5-export--integration-pipeline)
9. [Phase 6: Canvas & Spatial Features](#9-phase-6-canvas--spatial-features)
10. [File-by-File Change Registry](#10-file-by-file-change-registry)
11. [Database Schema Changes](#11-database-schema-changes)
12. [API Contract Changes](#12-api-contract-changes)
13. [Testing & Verification Plan](#13-testing--verification-plan)
14. [Model Strategy](#14-model-strategy)
15. [Risk Register](#15-risk-register)

---

## 1. Current State Assessment

### What Already Works (DO NOT REBUILD)

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Navigator 2.0 (Deep Discovery) | `src/backend/app/services/swarm.py` L497-L1119 | Working | Plan->Graph->Retrieve->Reason->Critic->Synthesize with reflection loops |
| Cortex 2.0 (Broad Research) | `src/backend/app/services/swarm.py` L1126-L1683 | Working | Decompose->Execute->CrossCheck->Resolve->Synthesize |
| Hybrid RAG Retrieval | `src/backend/app/services/retrieval.py` | Working | Vector + entity + exact text + graph expansion |
| RAPTOR Hierarchy | `src/backend/app/services/raptor.py` | Working | L0/L1/L2 hierarchical summarization |
| Semantic Chunking | `src/backend/app/services/semantic_chunker.py` | Working | Rust-based semantic-text-splitter |
| Docling PDF Parsing | `src/backend/app/services/docling_parser.py` | Working | Optional, falls back to pdfplumber |
| FlashRank Reranking | `src/backend/app/services/rerank.py` | Working | Cross-encoder reranking |
| Model Hot-Swap | `src/backend/app/services/llm.py` L609-L674 | Working | Runtime GGUF model switching with VRAM cleanup |
| Prompt Templates | `src/backend/app/services/prompt_templates.py` | Working | Few-shot structured prompts |
| Knowledge Graph | `src/backend/app/services/graph.py` | Working | SQLite + NetworkX with caching |
| GLiNER NER | `src/backend/app/services/ingest.py` | Working | ONNX-accelerated entity extraction |
| Project Management | `src/backend/app/api/routes.py` | Working | CRUD for projects |
| File Management | `src/backend/app/api/routes.py` | Working | Upload, list, delete, serve PDFs |
| SQLite Schema | `src/backend/app/core/database.py` | Working | Project, Document, DocumentChunk, Node, Edge |

### What Needs Fixing (Technical Debt)

| Issue | File:Line | Severity | Fix |
|-------|-----------|----------|-----|
| No streaming - user waits 60-120s with no feedback | `routes.py:521-543` | **CRITICAL** | Add SSE streaming endpoint |
| n_ctx=4096 too small for complex prompts | `llm.py:341` | HIGH | Bump to 8192 or make configurable |
| Entity matching loads 100 nodes, filters in Python | `retrieval.py:155-161` | HIGH | Add FTS5 or proper SQL index |
| Router is binary (DEEP/BROAD), missing SIMPLE | `swarm.py:282-312` | HIGH | Add 3rd route for simple queries |
| No conversation memory / session state | N/A | HIGH | Add LangGraph checkpointing |
| `parse_json_response` silently returns `{}` on failure | `swarm.py:223-248` | MEDIUM | Add regex fallback parser |
| Session per query won't work with streaming | `retrieval.py:97-98` | MEDIUM | Async session context manager |
| Swarm response model missing new fields | `routes.py:80-85` | LOW | Add confidence_score, iterations, contradictions |

---

## 2. Architecture Overview

### Target Architecture: MoE Multi-Agent Research OS

```
┌─────────────────────────────────────────────────────────────────┐
│                    TAURI DESKTOP SHELL (Rust)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌──────────────────────┐  ┌───────────────┐ │
│  │   Living     │  │    Deep Work Canvas   │  │   Context      │ │
│  │   Library    │  │    (TipTap Editor)    │  │   Engine       │ │
│  │             │  │                      │  │   (Sidebar)    │ │
│  │  - Smart    │  │  - Block editor      │  │               │ │
│  │    groups   │  │  - AI suggestions    │  │  - Proactive   │ │
│  │  - Search   │  │  - Citation blocks   │  │    retrieval   │ │
│  │  - Zotero   │  │  - PDF snippets      │  │  - Mini graph  │ │
│  │    import   │  │                      │  │  - Suggestions │ │
│  └──────┬──────┘  └──────────┬───────────┘  └───────┬───────┘ │
│         │                    │                       │         │
│  ┌──────┴────────────────────┴───────────────────────┴───────┐ │
│  │              NEXT.JS FRONTEND (TypeScript)                 │ │
│  │  - React 18 + Zustand stores + SSE client                 │ │
│  │  - react-resizable-panels (3-pane layout)                 │ │
│  │  - @xyflow/react (graph viz) + TipTap (editor)           │ │
│  └────────────────────────┬──────────────────────────────────┘ │
│                           │ HTTP + SSE                         │
│  ┌────────────────────────┴──────────────────────────────────┐ │
│  │              FASTAPI BACKEND (Python)                      │ │
│  │                                                            │ │
│  │  ┌─────────────────────────────────────────────────────┐  │ │
│  │  │              META-ROUTER (MoE Supervisor)            │  │ │
│  │  │  - Classifies: SIMPLE | DEEP | BROAD | MULTI_STEP   │  │ │
│  │  └──────────┬──────────┬──────────┬──────────┬─────────┘  │ │
│  │             │          │          │          │             │ │
│  │  ┌──────────▼┐ ┌──────▼──────┐ ┌▼────────┐ ┌▼──────────┐│ │
│  │  │ Librarian │ │  Navigator  │ │ Cortex  │ │  Planner  ││ │
│  │  │ (Simple)  │ │  (Deep)     │ │ (Broad) │ │ (Multi)   ││ │
│  │  │           │ │             │ │         │ │           ││ │
│  │  │ Vector    │ │ Plan→Graph  │ │ Decomp  │ │ Orchestr. ││ │
│  │  │ search +  │ │ →Retrieve   │ │ →Execute│ │ multiple  ││ │
│  │  │ answer    │ │ →Reason     │ │ →Cross  │ │ agents    ││ │
│  │  │           │ │ →Verify     │ │  Check  │ │           ││ │
│  │  └─────┬─────┘ └──────┬─────┘ └────┬────┘ └─────┬─────┘│ │
│  │        └──────────────┬┴────────────┘            │      │ │
│  │                       │                          │      │ │
│  │  ┌────────────────────▼──────────────────────────▼────┐ │ │
│  │  │           SHARED SERVICES LAYER                    │ │ │
│  │  │                                                    │ │ │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │ │ │
│  │  │  │ Grounding│ │ Session  │ │  Model   │          │ │ │
│  │  │  │ Verifier │ │ Memory   │ │ Manager  │          │ │ │
│  │  │  │ (Critic) │ │ (Checkpt)│ │ (Swap)   │          │ │ │
│  │  │  └──────────┘ └──────────┘ └──────────┘          │ │ │
│  │  │                                                    │ │ │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │ │ │
│  │  │  │ Qdrant   │ │ SQLite   │ │ LLM      │          │ │ │
│  │  │  │ (Vector) │ │ (Graph+  │ │ Service  │          │ │ │
│  │  │  │          │ │  Docs)   │ │ (llama   │          │ │ │
│  │  │  │          │ │          │ │  cpp)    │          │ │ │
│  │  │  └──────────┘ └──────────┘ └──────────┘          │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 0: Foundation Fixes

**Goal**: Fix critical technical debt before building new features.
**Estimated effort**: 3-4 days
**Priority**: MUST DO FIRST

### Task 0.1: Increase Context Window

**File**: `src/backend/app/services/llm.py`
**Line**: 341

```python
# BEFORE:
self._llm = Llama(
    model_path=str(model_path),
    n_ctx=4096,  # Too small
    ...
)

# AFTER:
n_ctx = int(os.environ.get("ATLAS_N_CTX", "8192"))
self._llm = Llama(
    model_path=str(model_path),
    n_ctx=n_ctx,
    ...
)
```

**Also add to** `src/backend/app/core/config.py`:
```python
LLM_CONTEXT_SIZE: int = 8192
```

### Task 0.2: Fix Entity Matching Performance

**File**: `src/backend/app/services/retrieval.py`
**Lines**: 148-161

Current code loads 100 nodes and filters in Python. Replace with SQL-level filtering.

```python
# BEFORE:
nodes = node_query.limit(100).all()
matching_nodes = [
    n for n in nodes
    if entity_name.lower() in (n.properties or {}).get("name", "").lower()
]

# AFTER - Use SQLite JSON functions:
from sqlalchemy import func
matching_nodes = node_query.filter(
    func.lower(func.json_extract(Node.properties, '$.name')).contains(entity_name.lower())
).limit(20).all()
```

### Task 0.3: Update SwarmResponse Model

**File**: `src/backend/app/api/routes.py`
**Lines**: 80-85

```python
class SwarmResponse(BaseModel):
    brain_used: str
    hypothesis: str
    evidence: List[Dict[str, Any]]
    reasoning_trace: List[str]
    status: str
    # NEW FIELDS (Navigator 2.0 / Cortex 2.0):
    confidence_score: Optional[float] = None
    iterations: Optional[int] = None
    contradictions: List[Dict[str, Any]] = []
```

### Task 0.4: Upgrade to Constrained Generation (Grammars)

**File**: `src/backend/app/services/llm.py` (add method)
**File**: `src/backend/app/services/swarm.py` (update usage)

Instead of regex fallback (unreliable), use `llama-cpp-python`'s grammar constraints to FORCE valid JSON output. This is faster (no retries) and 100% reliable.

```python
# In llm.py
from llama_cpp.llama_grammar import LlamaGrammar

def generate_constrained(self, prompt: str, schema: Dict[str, Any]) -> dict:
    """Generate JSON that strictly follows a JSON schema."""
    # Convert schema to GBNF grammar
    grammar = LlamaGrammar.from_json_schema(json.dumps(schema))
    
    response = self._llm(
        prompt,
        grammar=grammar,
        max_tokens=2048,
        temperature=0.1
    )
    return json.loads(response['choices'][0]['text'])
```

**Usage in agents**:
```python
# Define schema for the agent's expected output
NODE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["keep", "discard"]},
        "reasoning": {"type": "string"},
        "confidence": {"type": "number"}
    },
    "required": ["verdict", "reasoning"]
}

response = await llm.generate_constrained(prompt, NODE_SCHEMA)
# No parsing needed - response is already a dict
```

### Task 0.5: Enable Prompt Caching

**File**: `src/backend/app/services/llm.py`

**Critical Speedup**: For multi-turn chats, re-processing the entire context (4096+ tokens) on every turn is slow on CPU/Consumer GPU. Llama.cpp supports prompt caching.

```python
# In Llama initialization
self._llm = Llama(
    ...,
    n_ctx=8192,
    n_batch=512,
    use_mlock=True,       # Keep model in RAM
    check_tensors=False,  # Skip tensor checks for speed
    cache=True,           # Enable KV cache
    verbose=False
)
```

Also implement a `cache_prompt` logic if using `llama-cpp-python` server or stateful instance.

---

## 4. Phase 1: MoE Multi-Agent Backend

**Goal**: Transform the binary router into a true Mixture-of-Experts multi-agent system.
**Estimated effort**: 5-7 days
**Files created**: 2 new, 4 modified

### Task 1.1: Create the Librarian Agent (New Brain)

**New file**: `src/backend/app/services/agents/librarian.py`

The Librarian handles 80% of queries - simple factual lookups that don't need graph exploration or multi-turn reasoning. This makes the system feel 10x faster for common questions.

```python
"""
Librarian Agent - Fast factual retrieval for simple queries.

Architecture:
  Retrieve (vector search) -> Answer (single LLM call) -> Cite (source attribution)

This agent handles ~80% of queries in <5 seconds vs Navigator's 30-60s.
"""

from typing import Any, Dict, List
from langgraph.graph import StateGraph, END

class LibrarianState(TypedDict, total=False):
    query: str
    project_id: str
    brain: str
    chunks: List[Dict[str, Any]]
    answer: str
    citations: List[Dict[str, Any]]
    confidence_score: float
    reasoning_trace: List[str]
    status: str


def _build_librarian_graph(
    llm_service,
    qdrant_client,
    collection_name: str,
) -> StateGraph:
    """Simple 2-node graph: Retrieve -> Answer."""

    async def retrieve_node(state: LibrarianState) -> LibrarianState:
        """Vector search + rerank, no graph exploration."""
        trace = ["Librarian: Searching document library..."]

        embedding = await llm_service.embed(state["query"])
        results = qdrant_client.query_points(
            collection_name=collection_name,
            query=embedding,
            limit=8,
        ).points

        chunks = []
        for r in results:
            payload = r.payload or {}
            chunks.append({
                "text": payload.get("text", ""),
                "metadata": payload.get("metadata", {}),
                "score": r.score,
            })

        # Optional: rerank
        if settings.ENABLE_RERANKING and chunks:
            reranker = get_rerank_service()
            chunks = await reranker.rerank(
                query=state["query"],
                documents=chunks,
                top_n=5
            )

        trace.append(f"Found {len(chunks)} relevant passages")
        return {**state, "chunks": chunks, "reasoning_trace": trace}

    async def answer_node(state: LibrarianState) -> LibrarianState:
        """Single LLM call with retrieved context."""
        trace = list(state.get("reasoning_trace", []))
        chunks = state.get("chunks", [])

        if not chunks:
            return {
                **state,
                "answer": "I couldn't find relevant information in your documents.",
                "citations": [],
                "confidence_score": 0.0,
                "status": "completed",
                "reasoning_trace": trace + ["No relevant chunks found"],
            }

        context = format_chunks(chunks, max_chunks=5)

        prompt = f"""Answer this question using ONLY the provided evidence.
Cite every fact as [Source: filename, Page: X].

Question: {state["query"]}

Evidence:
{context}

If the evidence doesn't contain the answer, say "I cannot find this in your documents."

Answer:"""

        answer = await llm_service.generate(
            prompt=prompt, temperature=0.1, max_tokens=1024
        )

        citations = [
            {
                "source": c["metadata"].get("filename", "Unknown"),
                "page": c["metadata"].get("page", 1),
                "excerpt": c["text"][:200],
                "relevance": c.get("score", 0),
            }
            for c in chunks[:5]
        ]

        return {
            **state,
            "answer": answer.strip(),
            "citations": citations,
            "confidence_score": 0.7,  # Default for simple retrieval
            "status": "completed",
            "reasoning_trace": trace + ["Answer generated"],
        }

    graph = StateGraph(LibrarianState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    return graph
```

### Task 1.2: Upgrade Router to 4-Way MoE Classifier

**File**: `src/backend/app/services/swarm.py`
**Function**: `route_intent` (line 282)

Replace the binary DEEP/BROAD classifier with a 4-way MoE router:

```python
async def route_intent(query: str, llm_service) -> str:
    """Classify query into one of four agent types.

    SIMPLE         - Direct fact lookup, specific question about a document
    DEEP_DISCOVERY - Synthesis, connection-finding, hypothesis generation
    BROAD_RESEARCH - Survey, landscape scan, comparison across many sources
    MULTI_STEP     - Complex query requiring both deep and broad analysis
    """
    prompt = f"""Classify this research query into exactly ONE category:

SIMPLE - The user wants a specific fact, quote, or detail from their documents.
Examples: "What methodology did they use?", "What is the sample size in Table 2?"

DEEP_DISCOVERY - The user wants to find hidden connections, synthesize across domains,
generate hypotheses, or discover relationships.
Examples: "How might X relate to Y?", "What connections exist between these papers?"

BROAD_RESEARCH - The user wants a broad survey, comparison, or landscape overview.
Examples: "Compare the methods across all papers", "What approaches exist for X?"

MULTI_STEP - The query requires BOTH deep analysis AND broad comparison, or has
multiple distinct sub-questions that need different approaches.
Examples: "Find connections between X and Y, then compare with alternative approaches"

Query: {query}

Respond with ONLY the category name:"""

    try:
        response = await llm_service.generate(
            prompt=prompt, temperature=0.0, max_tokens=20
        )
        response = response.strip().upper()

        if "SIMPLE" in response:
            return "SIMPLE"
        elif "MULTI" in response:
            return "MULTI_STEP"
        elif "BROAD" in response:
            return "BROAD_RESEARCH"
        else:
            return "DEEP_DISCOVERY"
    except Exception as e:
        logger.warning(f"Router failed: {e}, defaulting to SIMPLE")
        return "SIMPLE"
```

### Task 1.3: Update `run_swarm_query` for MoE Dispatch

**File**: `src/backend/app/services/swarm.py`
**Function**: `run_swarm_query` (line 1880)

Add Librarian dispatch and multi-step orchestration:

```python
async def run_swarm_query(...) -> Dict[str, Any]:
    intent = await route_intent(query, llm_service)
    logger.info(f"MoE Router: {intent}")

    if intent == "SIMPLE":
        brain_name = "librarian"
        # Use the lightweight Librarian agent
        from app.services.agents.librarian import _build_librarian_graph
        initial_state = LibrarianState(...)
        sg = _build_librarian_graph(llm_service, qdrant_client, collection_name)

    elif intent == "DEEP_DISCOVERY":
        brain_name = "navigator"
        # Existing Navigator 2.0 code (unchanged)
        ...

    elif intent == "BROAD_RESEARCH":
        brain_name = "cortex"
        # Existing Cortex 2.0 code (unchanged)
        ...

    elif intent == "MULTI_STEP":
        brain_name = "orchestrator"
        # Phase 1.4: Multi-step orchestrator
        ...
```

### Task 1.4: Create Shared Grounding Verifier

**New file**: `src/backend/app/services/agents/grounding.py`

Extracted from Navigator's critic - now a shared service ANY agent can call.

```python
"""
Grounding Verifier - Shared anti-hallucination service.

Verifies that every claim in an AI response is actually supported
by the cited source text. Returns a verification report with
confidence badges per claim.

Badge levels:
  GROUNDED   - Claim directly supported by cited source
  SUPPORTED  - Claim paraphrased but source matches
  UNVERIFIED - No matching source found for this claim
  INFERRED   - Claim is a synthesis/inference, not in any source
"""

class GroundingVerifier:
    def __init__(self, llm_service, qdrant_client, collection_name):
        self.llm = llm_service
        self.qdrant = qdrant_client
        self.collection = collection_name

    async def verify_response(
        self,
        answer: str,
        cited_evidence: List[Dict],
        query: str,
    ) -> Dict[str, Any]:
        """Verify each claim in the answer against source text.

        Returns:
            {
                "verified_answer": str,  # Answer with inline verification markers
                "claims": [
                    {
                        "claim": "...",
                        "status": "GROUNDED|SUPPORTED|UNVERIFIED|INFERRED",
                        "source": "filename.pdf",
                        "page": 5,
                        "matching_text": "...",  # actual text from source
                        "confidence": 0.95
                    }
                ],
                "overall_grounding_score": 0.85  # % of claims that are grounded
            }
        """
        # Step 1: Extract individual claims from the answer
        claims = await self._extract_claims(answer)

        # Step 2: For each claim, find the cited source and verify
        verified_claims = []
        for claim in claims:
            verification = await self._verify_single_claim(
                claim, cited_evidence
            )
            verified_claims.append(verification)

        # Step 3: Calculate overall grounding score
        grounded = sum(1 for c in verified_claims
                       if c["status"] in ("GROUNDED", "SUPPORTED"))
        total = max(len(verified_claims), 1)

        return {
            "claims": verified_claims,
            "overall_grounding_score": grounded / total,
        }

    async def _extract_claims(self, answer: str) -> List[str]:
        """Use LLM to extract individual factual claims."""
        prompt = f"""Extract every factual claim from this text as a numbered list.
Only include claims that can be verified against a source document.
Skip opinions, transitions, and meta-commentary.

Text: {answer}

Claims:
1."""
        response = await self.llm.generate(
            prompt=prompt, temperature=0.0, max_tokens=1024
        )
        # Parse numbered list
        claims = re.findall(r'\d+\.\s*(.+)', response)
        return claims

    async def _verify_single_claim(
        self, claim: str, evidence: List[Dict]
    ) -> Dict:
        """Check if a single claim is supported by evidence."""
        # Search for the claim in the vector store
        embedding = await self.llm.embed(claim)
        results = self.qdrant.query_points(
            collection_name=self.collection,
            query=embedding,
            limit=3,
        ).points

        if not results or results[0].score < 0.5:
            return {
                "claim": claim,
                "status": "UNVERIFIED",
                "confidence": 0.0,
            }

        best_match = results[0]
        source_text = best_match.payload.get("text", "")
        metadata = best_match.payload.get("metadata", {})

        # Use LLM to check if the claim is actually supported
        prompt = f"""Does the source text support this claim? Answer ONLY with:
GROUNDED - claim is directly stated in the source
SUPPORTED - claim is a reasonable paraphrase of the source
INFERRED - claim goes beyond what the source says

Claim: {claim}
Source text: {source_text[:500]}

Verdict:"""

        verdict = await self.llm.generate(
            prompt=prompt, temperature=0.0, max_tokens=20
        )
        verdict = verdict.strip().upper()

        status = "GROUNDED"
        if "SUPPORTED" in verdict:
            status = "SUPPORTED"
        elif "INFERRED" in verdict:
            status = "INFERRED"

        return {
            "claim": claim,
            "status": status,
            "source": metadata.get("filename", "Unknown"),
            "page": metadata.get("page", 1),
            "matching_text": source_text[:200],
            "confidence": best_match.score,
        }
```

### Task 1.5: Add Session Memory with LangGraph Checkpointing

**File**: `src/backend/app/services/swarm.py` (modify)
**New file**: `src/backend/app/core/memory.py`

```python
# src/backend/app/core/memory.py
"""
Session memory using LangGraph checkpointing.
Persists conversation state across queries within a research session.
"""
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.core.config import settings

_memory_saver = None

async def get_memory_saver() -> AsyncSqliteSaver:
    """Get or create the singleton checkpoint saver."""
    global _memory_saver
    if _memory_saver is None:
        _memory_saver = AsyncSqliteSaver.from_conn_string(
            settings.DATABASE_PATH.replace(".db", "_memory.db")
        )
    return _memory_saver
```

**Integration in swarm.py**:
```python
# When compiling the graph:
memory = await get_memory_saver()
compiled = sg.compile(checkpointer=memory)

# When invoking:
config = {"configurable": {"thread_id": session_id}}
final_state = await compiled.ainvoke(initial_state, config=config)
```

### Task 1.6: Add Automatic Model Swapping in Router

**File**: `src/backend/app/services/swarm.py`

When the router selects DEEP_DISCOVERY or BROAD_RESEARCH, check if the "deep" model is loaded. If not, swap models before running the agent.

```python
async def _ensure_optimal_model(intent: str, llm_service):
    """Swap to the optimal model for the task if needed."""
    available = llm_service.list_available_models()
    current = llm_service.active_model_name

    # Define model preferences per intent
    DEEP_MODELS = ["deepseek", "qwen2.5-7b", "llama-3-8b"]
    FAST_MODELS = ["phi-3.5", "qwen2.5-3b", "llama-3.2-3b"]

    if intent in ("DEEP_DISCOVERY", "BROAD_RESEARCH", "MULTI_STEP"):
        # Prefer a larger model
        for preferred in DEEP_MODELS:
            match = next((m for m in available if preferred in m.lower()), None)
            if match and match != current:
                logger.info(f"Swapping to deep model: {match}")
                await llm_service.load_model(match)
                return
    elif intent == "SIMPLE":
        # Prefer a faster model (if a smaller one is available)
        for preferred in FAST_MODELS:
            match = next((m for m in available if preferred in m.lower()), None)
            if match and match != current:
                logger.info(f"Swapping to fast model: {match}")
                await llm_service.load_model(match)
                return
```

### Task 1.7: Create Agent Package Structure

Create proper Python package for agents:

```
src/backend/app/services/agents/
├── __init__.py
├── librarian.py      # Task 1.1
├── grounding.py      # Task 1.4
├── meta_router.py    # Task 1.2 (extracted from swarm.py)
└── orchestrator.py   # Multi-step orchestrator (future)
```

### Task 1.8: Graph Library Optimization

**File**: `src/backend/app/services/graph.py`

**Critical Speedup**: `networkx` is slow for 10k+ nodes.
Migrate heavy graph algorithms (e.g., connected components, shorttest path) to **Rustworkx** (Drop-in replacement, written in Rust, 50x faster).

```bash
pip install rustworkx
```

```python
import rustworkx as rx
# Use rx.PyDiGraph instead of nx.DiGraph
```

---

## 5. Phase 2: Streaming & Real-Time UX

**Goal**: Users see reasoning progress in real-time instead of staring at a spinner.
**Estimated effort**: 4-5 days
**Files created**: 1 new, 3 modified

### Task 2.1: Add SSE Streaming Endpoint

**File**: `src/backend/app/api/routes.py` (add new endpoint)

```python
from fastapi.responses import StreamingResponse
import json

class SwarmStreamRequest(BaseModel):
    project_id: str
    query: str
    session_id: Optional[str] = None  # For memory persistence

@router.post("/api/swarm/stream")
async def stream_swarm(request: SwarmStreamRequest):
    """Stream swarm execution via Server-Sent Events.

    Event types:
      - routing:  {"brain": "navigator", "intent": "DEEP_DISCOVERY"}
      - progress: {"node": "planner", "message": "Planning research strategy..."}
      - thinking: {"content": "Step 1: Analyzing the query..."}
      - chunk:    {"content": "partial answer text"}  (token streaming)
      - evidence: {"source": "file.pdf", "page": 5, "excerpt": "..."}
      - grounding: {"claim": "...", "status": "GROUNDED", "confidence": 0.9}
      - complete: {"hypothesis": "full answer", "confidence": 0.85, ...}
      - error:    {"message": "..."}
    """
    ensure_services()

    async def event_generator():
        try:
            from app.services.swarm import run_swarm_query_streaming

            async for event_type, event_data in run_swarm_query_streaming(
                query=request.query,
                project_id=request.project_id,
                session_id=request.session_id,
                graph_service=graph_service,
                llm_service=chat_service.retrieval_service.llm_service,
                qdrant_client=chat_service.retrieval_service.qdrant_client,
                collection_name=chat_service.retrieval_service.collection_name,
            ):
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### Task 2.2: Add Streaming to Swarm Execution

**File**: `src/backend/app/services/swarm.py` (add function)

```python
async def run_swarm_query_streaming(
    query, project_id, session_id, graph_service, llm_service,
    qdrant_client, collection_name
):
    """Streaming version of run_swarm_query.

    Yields (event_type, event_data) tuples as the graph executes.
    Uses LangGraph's astream_events() for node-level progress.
    """
    # Step 1: Route
    intent = await route_intent(query, llm_service)
    yield ("routing", {"brain": intent, "intent": intent})

    # Step 2: Build graph (same as before)
    # ... (existing dispatch logic) ...

    compiled = sg.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": session_id or str(uuid.uuid4())}}

    # Step 3: Stream execution
    async for event in compiled.astream_events(initial_state, config=config, version="v2"):
        kind = event["event"]

        if kind == "on_chain_start":
            node_name = event.get("name", "")
            yield ("progress", {
                "node": node_name,
                "message": _get_progress_message(node_name)
            })

        elif kind == "on_chain_end":
            node_name = event.get("name", "")
            output = event.get("data", {}).get("output", {})

            # Emit reasoning trace updates
            trace = output.get("reasoning_trace", [])
            if trace:
                yield ("thinking", {"content": trace[-1] if trace else ""})

            # Emit evidence as it's found
            evidence = output.get("evidence", [])
            for ev in evidence:
                yield ("evidence", ev)

    # Step 4: Emit final result
    final_state = await compiled.ainvoke(initial_state, config=config)
    yield ("complete", {
        "hypothesis": final_state.get("final_answer") or final_state.get("hypothesis", ""),
        "evidence": final_state.get("evidence", []),
        "confidence_score": final_state.get("confidence_score"),
        "reasoning_trace": final_state.get("reasoning_trace", []),
        "brain_used": brain_name,
        "status": final_state.get("status", "completed"),
    })


def _get_progress_message(node_name: str) -> str:
    """Human-readable progress messages for each node."""
    messages = {
        "planner": "Planning research strategy...",
        "graph_explorer": "Exploring knowledge graph...",
        "retriever": "Searching document library...",
        "reasoner": "Synthesizing hypothesis...",
        "critic": "Verifying claims against sources...",
        "synthesizer": "Preparing final answer...",
        "decomposer": "Breaking down the question...",
        "executor": "Researching sub-questions...",
        "cross_checker": "Cross-checking findings...",
        "resolver": "Resolving contradictions...",
        "retrieve": "Searching for relevant passages...",
        "answer": "Generating answer...",
    }
    return messages.get(node_name, f"Processing: {node_name}...")
```

### Task 2.3: Frontend SSE Client

**File**: `src/frontend/lib/api.ts` (add method)

```typescript
// Add to api object:

streamSwarm(
    query: string,
    projectId: string,
    sessionId: string | undefined,
    callbacks: {
        onRouting?: (data: { brain: string; intent: string }) => void;
        onProgress?: (data: { node: string; message: string }) => void;
        onThinking?: (data: { content: string }) => void;
        onEvidence?: (data: SwarmEvidence) => void;
        onGrounding?: (data: { claim: string; status: string; confidence: number }) => void;
        onComplete?: (data: SwarmResponse) => void;
        onError?: (data: { message: string }) => void;
    }
): () => void {  // Returns abort function
    const controller = new AbortController();

    fetch(`${API_BASE_URL}/api/swarm/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, project_id: projectId, session_id: sessionId }),
        signal: controller.signal,
    }).then(async (response) => {
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (reader) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            let currentEvent = '';
            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    currentEvent = line.slice(7);
                } else if (line.startsWith('data: ') && currentEvent) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        const handler = callbacks[`on${currentEvent.charAt(0).toUpperCase() + currentEvent.slice(1)}` as keyof typeof callbacks];
                        if (handler) (handler as Function)(data);
                    } catch {}
                    currentEvent = '';
                }
            }
        }
    }).catch((err) => {
        if (err.name !== 'AbortError') {
            callbacks.onError?.({ message: err.message });
        }
    });

    return () => controller.abort();
},
```

### Task 2.4: Update DualAgentChat for Streaming

**File**: `src/frontend/components/DualAgentChat.tsx`

Replace the current `await api.runSwarm()` call with `api.streamSwarm()` that shows:
- A "thinking" indicator with the current agent step
- The reasoning trace building up in real-time
- Evidence cards appearing as they're found
- The final answer streaming in token-by-token

Key changes:
- Add `StreamingMessage` component that renders partial results
- Add `ThinkingIndicator` component showing current node ("Searching graph...")
- Add `EvidenceCardStream` that shows sources as they arrive
- Replace `isLoading` boolean with a `streamState` object tracking progress

### Task 2.5: Visual "Thinking Tracks"

**Enhancement**: Don't just show text logs. Visualize the agent's path through the graph.

**File**: `src/frontend/components/ThinkingTracks.tsx`

Implementation:
- Overlay a simplified partial Knowledge Graph on the chat UI during execution.
- Animate the active node (Agent) "hopping" between concepts (Entity A -> Paper B -> Concept C).
- Allow user to pause/redirect: Click a node to say "Focus here" or "Avoid this path".

---

## 6. Phase 3: Research OS Frontend

**Goal**: Transform from single-chat to Advanced Research OS layout.
**Estimated effort**: 7-10 days
**Files created**: 5-8 new components, 2-3 modified

### Task 3.1: New 3-Pane Layout

**File**: `src/frontend/app/project/workspace-page.tsx` (rewrite)

The current layout uses `react-resizable-panels` (already installed). Restructure to:

```
┌──────────────┬────────────────────────┬──────────────┐
│   Living     │                        │   Context    │
│   Library    │    Center Pane         │   Engine     │
│              │    (PDF / Editor /     │   (Right)    │
│   - Smart    │     Graph / Chat)      │              │
│     file     │                        │  - Related   │
│     groups   │    Tabs:               │    passages  │
│   - Search   │    [Doc] [Edit] [Graph]│  - Mini      │
│   - Upload   │    [Chat]              │    graph     │
│              │                        │  - AI        │
│              │                        │    suggest   │
└──────────────┴────────────────────────┴──────────────┘
```

```tsx
// Simplified structure:
<PanelGroup direction="horizontal">
  {/* Left: Living Library */}
  <Panel defaultSize={20} minSize={15}>
    <LibrarySidebar projectId={projectId} />
  </Panel>

  <PanelResizeHandle />

  {/* Center: Main Work Area + Living Canvas */}
  <Panel defaultSize={55} minSize={30}>
    <WorkspaceTabs activeTab={activeTab} onTabChange={setActiveTab}>
      <PDFViewer />
      <EditorPane />      {/* Phase 3.3: TipTap + Ghost Text */}
      <KnowledgeGraph />
      {/* Living Canvas Overlay for spatial mode */}
      <LivingCanvas active={viewMode === 'canvas'} /> 
      <ChatPane />
    </WorkspaceTabs>
  </Panel>

  <PanelResizeHandle />

  {/* Right: Augmented Margin / Context Engine */}
  <Panel defaultSize={25} minSize={15} collapsible>
    <ContextEngine projectId={projectId} activeContext={activeContext} />
  </Panel>
</PanelGroup>
```

**New Feature: "Living Canvas" (Mini-Canvas)**
- Allow any tab (PDF, Chat, Graph) to be "popped out" into a floating card.
- Basic spatial organization: Drag cards side-by-side for comparison.
- "Compare" action spawns a canvas with target documents pre-arranged.

### Task 3.2: Living Library Component

**New file**: `src/frontend/components/LibrarySidebar.tsx`

Replace the current `FileSidebar.tsx` with a smarter library that:
- Groups papers by topic (using knowledge graph clusters)
- Shows ingestion status per document
- Has search across all documents
- Has a "Smart Groups" section that auto-clusters by entity overlap
- Drag-and-drop upload zone

```tsx
interface LibrarySidebarProps {
  projectId: string;
}

// Key features:
// 1. Search bar at top that searches across all document text
// 2. "Smart Groups" section showing auto-generated topic clusters
//    (from RAPTOR L2 summaries + graph connected components)
// 3. "All Documents" flat list with status indicators
// 4. Right-click context menu: "View", "Delete", "Compare with..."
// 5. Drag-drop upload zone at bottom
```

### Task 3.3: TipTap Block Editor

**New file**: `src/frontend/components/EditorPane.tsx`

Install TipTap and create a research-focused block editor:

```bash
npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-placeholder
npm install @tiptap/extension-link @tiptap/extension-highlight
npm install @tiptap/extension-task-list @tiptap/extension-task-item
```

```tsx
// EditorPane.tsx - Research document editor
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

// Custom extensions to build:
// 1. CitationBlock - renders as [Author, Year] with hover card
// 2. AIInsertBlock - shows AI-generated content with verification badges
// 3. PDFSnippetBlock - embedded excerpt from a PDF with source link
// 4. "Ghost Text" - inline AI completion (greyed out), Tab to accept
//    - Suggests citations based on context
//    - Auto-completes arguments using graph facts

export default function EditorPane({ projectId }: { projectId: string }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: 'Start writing your research notes...' }),
      Link, Highlight, TaskList, TaskItem,
      // Custom: CitationExtension, AIInsertExtension, GhostTextExtension
    ],
    content: '',
  });

  return (
    <div className="editor-container">
      <EditorToolbar editor={editor} />
      <EditorContent editor={editor} className="prose prose-sm" />
    </div>
  );
}
```

### Task 3.4: Augmented Margin & Context Engine

**Upgrade**: Transform passive sidebar into an active "Augmented Margin".

**New file**: `src/frontend/components/AugmentedMargin.tsx`

Instead of looking away to a sidebar, the AI places interactive bubbles *alongside* the text.

```tsx
interface ContextEngineProps {
  projectId: string;
  activeContext: {
    type: 'pdf' | 'editor' | 'graph' | 'chat';
    selectedText?: string;
    currentPage?: number;
    currentDocId?: string;
  };
}

// Features:
// 1. "Contradiction Bubble": Appears next to a claim that contradicts another paper.
// 2. "Connection Bubble": Links to a related concept in the graph.
// 3. "Definition Bubble": Expands acronyms or complex terms on hover.
// 4. Zero Prompt: Bubbles appear automatically as you read (proactive).
```

### Task 3.5: Generative UI Components

**New files**:
- `src/frontend/components/generative/ComparisonTable.tsx`
- `src/frontend/components/generative/CitationCard.tsx`
- `src/frontend/components/generative/ClaimBadge.tsx`

The AI can generate structured responses that render as interactive components:

```tsx
// ComparisonTable - when AI compares methods/papers
interface ComparisonTableProps {
  headers: string[];
  rows: Array<{ cells: string[]; sources: Citation[] }>;
  title: string;
}

// CitationCard - hover preview for any citation
interface CitationCardProps {
  source: string;
  page: number;
  abstract?: string;
  keyFindings?: string[];
  groundingStatus: 'GROUNDED' | 'SUPPORTED' | 'UNVERIFIED' | 'INFERRED';
}

// ClaimBadge - inline verification indicator
interface ClaimBadgeProps {
  status: 'GROUNDED' | 'SUPPORTED' | 'UNVERIFIED' | 'INFERRED';
  claim: string;
  source?: string;
  onClick?: () => void;  // Navigate to source
}
// Renders as colored dot: green/yellow/red/gray
```

---

## 7. Phase 4: Smart Reading & Context Engine

**Goal**: Make Atlas the best PDF reading experience for researchers.
**Estimated effort**: 5-7 days

### Task 4.1: Auto-Extract Paper Structure on Ingestion

**File**: `src/backend/app/services/ingest.py` (modify)

During ingestion, auto-extract structured metadata:

```python
async def _extract_paper_structure(self, text: str, filename: str) -> Dict:
    """Extract structured academic paper metadata."""
    prompt = f"""Extract the following from this academic paper. Return JSON:
{{
    "title": "paper title",
    "authors": ["author 1", "author 2"],
    "year": 2024,
    "abstract": "abstract text",
    "methodology": "brief description of methods used",
    "key_findings": ["finding 1", "finding 2"],
    "limitations": ["limitation 1"],
    "paper_type": "empirical|review|theoretical|meta-analysis"
}}

Paper text (first 3000 chars):
{text[:3000]}

JSON:"""

    response = await self.llm_service.generate(
        prompt=prompt, temperature=0.1, max_tokens=1024
    )
    return parse_json_response(response)
```

Store this in `Document.doc_metadata` (already exists in schema).

### Task 4.2: Paper Structure API Endpoint

**File**: `src/backend/app/api/routes.py` (add)

```python
@router.get("/files/{doc_id}/structure")
async def get_document_structure(doc_id: str):
    """Get extracted paper structure (title, authors, methods, findings)."""
    # Return doc_metadata from the Document record
    ...

@router.get("/files/{doc_id}/related")
async def get_related_passages(doc_id: str, text: str = Query(...)):
    """Find passages in other documents related to selected text."""
    # Embed the selected text, search Qdrant excluding this doc_id
    ...
```

### Task 4.3: Smart PDF Viewer Sidebar

**File**: `src/frontend/components/PDFViewer.tsx` (modify)

Add a sidebar panel when viewing PDFs that shows:
- Paper metadata (title, authors, year)
- Key findings extracted during ingestion
- Methodology summary
- "Ask about this page" quick-chat

### Task 4.4: Context-Aware Retrieval

**New file**: `src/backend/app/services/context_engine.py`

Backend service that accepts a "context snapshot" from the frontend and returns relevant information:

```python
class ContextEngine:
    """Proactive context-aware retrieval.

    Receives user's current context (selected text, active document,
    current page) and returns relevant passages, concepts, and suggestions.
    """

    async def get_context_suggestions(
        self,
        selected_text: Optional[str],
        current_doc_id: Optional[str],
        current_page: Optional[int],
        project_id: str,
    ) -> Dict[str, Any]:
        """Return context-aware suggestions."""
        results = {
            "related_passages": [],
            "connected_concepts": [],
            "suggestions": [],
        }

        if selected_text:
            # Find similar passages in OTHER documents
            results["related_passages"] = await self._find_similar(
                selected_text, project_id, exclude_doc=current_doc_id
            )

            # Find connected entities
            results["connected_concepts"] = await self._find_connected_entities(
                selected_text, project_id
            )

        return results
```

---

## 8. Phase 5: Export & Integration Pipeline

**Goal**: Get research OUT of Atlas and INTO papers.
**Estimated effort**: 3-4 days

### Task 5.1: Zotero/BibTeX Import

**New file**: `src/backend/app/services/importers/bibtex.py`

```python
"""Import papers from BibTeX/RIS files (Zotero/Mendeley export)."""
import bibtexparser  # pip install bibtexparser

class BibTeXImporter:
    async def import_file(self, bib_path: str, project_id: str) -> List[Dict]:
        """Parse .bib file and create Document records for each entry."""
        with open(bib_path) as f:
            bib_db = bibtexparser.load(f)

        imported = []
        for entry in bib_db.entries:
            doc_metadata = {
                "title": entry.get("title", ""),
                "authors": entry.get("author", "").split(" and "),
                "year": entry.get("year", ""),
                "journal": entry.get("journal", ""),
                "doi": entry.get("doi", ""),
                "bibtex_key": entry.get("ID", ""),
                "abstract": entry.get("abstract", ""),
            }
            imported.append(doc_metadata)
            # Create Document record with status="metadata_only"
            # (PDF can be attached later)

        return imported
```

### Task 5.2: BibTeX Export

**New file**: `src/backend/app/services/exporters/bibtex.py`

```python
"""Export citations from Atlas in BibTeX format."""

class BibTeXExporter:
    def export_project(self, project_id: str) -> str:
        """Export all documents in a project as a .bib file."""
        ...

    def export_citations(self, citation_ids: List[str]) -> str:
        """Export specific citations as BibTeX entries."""
        ...

    def format_citation(self, doc_metadata: Dict, style: str = "apa") -> str:
        """Format a single citation in APA/MLA/Chicago style."""
        ...
```

### Task 5.3: Markdown/Pandoc Export

**New file**: `src/backend/app/services/exporters/markdown.py`

```python
"""Export research synthesis as structured Markdown.
Compatible with Pandoc for LaTeX/PDF/DOCX conversion."""

class MarkdownExporter:
    def export_synthesis(
        self,
        content: str,          # From TipTap editor
        citations: List[Dict], # Referenced sources
        project_id: str,
    ) -> str:
        """Export editor content + citations as academic Markdown."""
        # Add YAML front matter for Pandoc
        # Convert citation blocks to Pandoc citation syntax [@key]
        # Generate bibliography section
        ...
```

### Task 5.4: Import/Export API Endpoints

**File**: `src/backend/app/api/routes.py` (add)

```python
@router.post("/import/bibtex")
async def import_bibtex(file: UploadFile, project_id: str = Query(...)):
    """Import papers from a BibTeX file."""
    ...

@router.get("/export/bibtex/{project_id}")
async def export_bibtex(project_id: str):
    """Export all project citations as BibTeX."""
    ...

@router.post("/export/markdown")
async def export_markdown(body: ExportRequest):
    """Export synthesis as Pandoc-compatible Markdown."""
    ...
```

---

## 9. Phase 6: Canvas & Spatial Features

**Goal**: Add infinite canvas for spatial research organization.
**Estimated effort**: 7-10 days
**Note**: This is POST-PILOT. Do not start before Phases 0-5 are stable.

### Task 6.1: Install @xyflow/react

```bash
cd src/frontend
npm install @xyflow/react
```

### Task 6.2: Canvas Component

**New file**: `src/frontend/components/ResearchCanvas.tsx`

An infinite canvas where users can:
- Place document cards (drag from library)
- Place AI insight cards
- Draw connections between cards
- Add text annotation blocks
- Group cards into clusters
- Zoom/pan freely

### Task 6.3: Canvas Persistence

Store canvas state (node positions, connections, annotations) in SQLite:

```python
# New model in database.py:
class CanvasState(Base):
    __tablename__ = "canvas_states"
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"))
    state_json = Column(JSON)  # @xyflow serialized state
    updated_at = Column(DateTime)
```

---

## 10. File-by-File Change Registry

### Backend Files to CREATE

| File | Phase | Purpose |
|------|-------|---------|
| `src/backend/app/services/agents/__init__.py` | 1 | Agent package init |
| `src/backend/app/services/agents/librarian.py` | 1 | Fast retrieval agent |
| `src/backend/app/services/agents/grounding.py` | 1 | Citation verification |
| `src/backend/app/services/agents/meta_router.py` | 1 | 4-way MoE classifier |
| `src/backend/app/core/memory.py` | 1 | LangGraph checkpointing |
| `src/backend/app/services/context_engine.py` | 4 | Proactive context retrieval |
| `src/backend/app/services/importers/__init__.py` | 5 | Importer package |
| `src/backend/app/services/importers/bibtex.py` | 5 | BibTeX/RIS import |
| `src/backend/app/services/exporters/__init__.py` | 5 | Exporter package |
| `src/backend/app/services/exporters/bibtex.py` | 5 | BibTeX export |
| `src/backend/app/services/exporters/markdown.py` | 5 | Markdown export |

### Backend Files to MODIFY

| File | Phase | Changes |
|------|-------|---------|
| `src/backend/app/services/llm.py` | 0 | Configurable n_ctx, add n_ctx to config |
| `src/backend/app/services/retrieval.py` | 0 | Fix entity matching SQL, async session |
| `src/backend/app/services/swarm.py` | 0,1,2 | Fix JSON parser, 4-way router, streaming, librarian dispatch |
| `src/backend/app/api/routes.py` | 0,2,4,5 | Update SwarmResponse, add SSE endpoint, context API, import/export |
| `src/backend/app/core/config.py` | 0,1 | Add LLM_CONTEXT_SIZE, session memory config |
| `src/backend/app/core/database.py` | 4,6 | Add SessionMessage model (memory), CanvasState model |
| `src/backend/app/services/ingest.py` | 4 | Add paper structure extraction |

### Frontend Files to CREATE

| File | Phase | Purpose |
|------|-------|---------|
| `src/frontend/components/LibrarySidebar.tsx` | 3 | Smart document library |
| `src/frontend/components/EditorPane.tsx` | 3 | TipTap block editor |
| `src/frontend/components/ContextEngine.tsx` | 3 | Right sidebar context engine |
| `src/frontend/components/WorkspaceTabs.tsx` | 3 | Tab switcher for center pane |
| `src/frontend/components/StreamingMessage.tsx` | 2 | Streaming chat message renderer |
| `src/frontend/components/ThinkingIndicator.tsx` | 2 | Agent progress indicator |
| `src/frontend/components/generative/ComparisonTable.tsx` | 3 | AI-generated comparison table |
| `src/frontend/components/generative/CitationCard.tsx` | 3 | Hover citation preview |
| `src/frontend/components/generative/ClaimBadge.tsx` | 3 | Verification status badge |
| `src/frontend/components/ResearchCanvas.tsx` | 6 | Infinite canvas (post-pilot) |

### Frontend Files to MODIFY

| File | Phase | Changes |
|------|-------|---------|
| `src/frontend/lib/api.ts` | 2,4,5 | Add streamSwarm, context API, import/export API |
| `src/frontend/components/DualAgentChat.tsx` | 2 | Replace fetch with streaming, add progress UI |
| `src/frontend/app/project/workspace-page.tsx` | 3 | Rewrite to 3-pane layout |
| `src/frontend/components/PDFViewer.tsx` | 4 | Add smart sidebar, text selection handler |
| `src/frontend/stores/chatStore.ts` | 2 | Add streaming state management |

### Frontend Packages to INSTALL

```bash
# Phase 3: Editor
npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-placeholder
npm install @tiptap/extension-link @tiptap/extension-highlight
npm install @tiptap/extension-task-list @tiptap/extension-task-item

# Phase 6: Canvas (post-pilot)
npm install @xyflow/react
```

### Backend Packages to INSTALL

```bash
# Phase 1: Memory
pip install langgraph-checkpoint-sqlite

# Phase 5: Import/Export
pip install bibtexparser
```

---

## 11. Database Schema Changes

### New Table: `session_messages` (Phase 1)

For conversation memory within research sessions.

```sql
CREATE TABLE session_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    project_id TEXT REFERENCES projects(id),
    role TEXT NOT NULL,  -- 'user' | 'assistant' | 'system'
    content TEXT NOT NULL,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_session_messages_session ON session_messages(session_id);
```

### New Table: `canvas_states` (Phase 6)

```sql
CREATE TABLE canvas_states (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    state_json JSON NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Modified Table: `documents` (Phase 4)

The `doc_metadata` JSON column will now store extracted paper structure:

```json
{
    "title": "Paper Title",
    "authors": ["Author 1", "Author 2"],
    "year": 2024,
    "abstract": "...",
    "methodology": "...",
    "key_findings": ["..."],
    "limitations": ["..."],
    "paper_type": "empirical",
    "bibtex_key": "smith2024",
    "doi": "10.1234/..."
}
```

No schema change needed - `doc_metadata` column already exists.

---

## 12. API Contract Changes

### New Endpoints

| Method | Path | Phase | Purpose |
|--------|------|-------|---------|
| POST | `/api/swarm/stream` | 2 | SSE streaming swarm execution |
| GET | `/files/{doc_id}/structure` | 4 | Get extracted paper structure |
| GET | `/files/{doc_id}/related?text=...` | 4 | Find related passages across docs |
| POST | `/api/context` | 4 | Get context-aware suggestions |
| POST | `/import/bibtex?project_id=...` | 5 | Import BibTeX file |
| GET | `/export/bibtex/{project_id}` | 5 | Export project as BibTeX |
| POST | `/export/markdown` | 5 | Export synthesis as Markdown |
| GET | `/api/sessions/{session_id}/messages` | 1 | Get conversation history |

### Modified Endpoints

| Method | Path | Phase | Change |
|--------|------|-------|--------|
| POST | `/api/swarm/run` | 0 | Add confidence_score, iterations, contradictions to response |
| POST | `/chat` | 1 | Add session_id parameter for memory |

---

## 13. Testing & Verification Plan

### Phase 0 Verification

- [ ] LLM loads with 8192 context without OOM on RTX 3050
- [ ] Entity matching query runs in <100ms with 5000 nodes
- [ ] JSON parser fallback correctly extracts fields from malformed output
- [ ] SwarmResponse includes new fields without breaking existing frontend

### Phase 1 Verification

- [ ] Librarian answers simple factual queries in <5 seconds
- [ ] Router correctly classifies: "What is X?" -> SIMPLE, "How does X relate to Y?" -> DEEP
- [ ] Grounding verifier flags hallucinated citations (test with known-bad output)
- [ ] Session memory persists across queries within same session
- [ ] Model swap completes without VRAM leak (check nvidia-smi before/after)

### Phase 2 Verification

- [ ] SSE stream delivers events in <500ms intervals during swarm execution
- [ ] Frontend shows progress messages as agents execute
- [ ] Stream handles disconnect gracefully (user closes tab)
- [ ] Final result matches non-streaming endpoint output

### Phase 3 Verification

- [ ] 3-pane layout renders correctly at 1920x1080 and 1366x768
- [ ] Panels resize without breaking child components
- [ ] TipTap editor saves/loads content correctly
- [ ] Context engine returns results in <2 seconds

### Duke Pilot Acceptance Criteria

1. **Speed**: Simple queries answered in <5 seconds, complex in <60 seconds
2. **Accuracy**: >90% of citations link to correct source text
3. **Adoption**: Users can import Zotero library and start asking questions in <5 minutes
4. **Trust**: Every AI claim shows verification badge (green/yellow/red/gray)
5. **Hardware**: Runs on RTX 3050 laptop with <4GB VRAM in fast mode

---

## 14. Model Strategy

### Recommended Model Stack (RTX 3050, 4GB VRAM)

| Role | Model | Quantization | VRAM | When Loaded |
|------|-------|-------------|------|-------------|
| Fast (default) | Qwen 2.5-3B-Instruct | Q4_K_M | ~2.5 GB | Always |
| Deep (on-demand) | Qwen 2.5-7B-Instruct | Q4_K_M | ~4.5 GB* | DEEP/BROAD queries |
| Embeddings | nomic-embed-text-v1.5 | FP32 | ~0.5 GB CPU | Always (CPU) |
| NER | GLiNER small-v2.1 | ONNX | ~0.2 GB CPU | During ingestion |

*Deep model uses CPU offload for layers that don't fit in VRAM.
**Ensure to launch llamas with `-fa` (Flash Attention) for 2x inference speed.**

### Model Priority Detection (already in llm.py)

Current priority order in `_load_llm`:
1. Phi-3.5-mini-instruct*.gguf
2. Qwen2.5-3B-Instruct*.gguf
3. llama-3-8b-instruct*.gguf

**Update to**:
1. Qwen2.5-3B-Instruct*.gguf (fast default)
2. Phi-3.5-mini-instruct*.gguf (fast alternative)
3. Qwen2.5-7B-Instruct*.gguf (deep)
4. DeepSeek-R1-Distill*.gguf (deep alternative)
5. llama-3-8b-instruct*.gguf (legacy fallback)

### Scaling Tiers

| GPU | Fast Model | Deep Model |
|-----|-----------|------------|
| RTX 3050 (4GB) | Qwen 2.5-3B Q4 | Qwen 2.5-7B Q4 (partial CPU) |
| RTX 3060 (8GB) | Qwen 2.5-3B Q4 | Qwen 2.5-14B Q4 |
| RTX 3090 (24GB) | Qwen 2.5-7B Q8 | DeepSeek-R1-Distill-32B Q4 |
| RTX 4090 (24GB) | Qwen 2.5-7B Q8 | Llama 3 70B Q4 |

---

## 15. Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Context window overflow with large documents | Crashes/truncation | HIGH | Phase 0.1: Configurable n_ctx + token counting before prompt assembly |
| LLM generates malformed JSON >30% of time | Agent pipeline fails | MEDIUM | Phase 0.4: Regex fallback parser + validation retries |
| Streaming SSE disconnects mid-generation | Lost results | MEDIUM | Phase 2: Save intermediate state to checkpointer, allow resume |
| Model swap takes >10s, blocks other queries | UX freeze | MEDIUM | Phase 1.6: Non-blocking swap with queue, show "Model loading..." UI |
| TipTap editor conflicts with Tauri webview | Editor doesn't work | LOW | Test early in Phase 3, fallback to textarea-based editor |
| Grounding verifier doubles LLM calls per query | Too slow | MEDIUM | Make grounding optional (config flag), cache verified claims |
| SQLite write contention with concurrent sessions | Data corruption | LOW | Use WAL mode (already common), add connection pooling |
| RAPTOR hierarchy generation slow on 50+ papers | Ingestion too slow | MEDIUM | Make RAPTOR async background task, show progress bar |

---

## Implementation Order Summary

```
Phase 0 (Days 1-3):   Foundation fixes - n_ctx, entity SQL, JSON parser, response model
Phase 1 (Days 4-10):  MoE backend - Librarian, 4-way router, grounding, memory, model swap
Phase 2 (Days 11-15): Streaming - SSE endpoint, swarm streaming, frontend SSE client
Phase 3 (Days 16-25): Research OS UI - 3-pane layout, library, TipTap editor, context engine
Phase 4 (Days 26-30): Smart reading - paper extraction, related passages, PDF sidebar
Phase 5 (Days 31-34): Export pipeline - BibTeX import/export, Markdown export
Phase 6 (Post-pilot): Canvas - @xyflow/react infinite canvas, spatial features
```

### Delegation Matrix: Who does what?

| Phase | Description | Optimal Agent | Why? |
|-------|-------------|---------------|------|
| **0. Foundation** | Setup & Refactor | **Cursor Pro (Claude 3.5)** | Fast, context-aware edits for simple refactors. |
| **1. MoE Backend** | Complex Logic (LangGraph) | **Antigravity (Gemini)** | Large context window for reasoning about whole-system architecture. |
| **2. Streaming** | Async Python + Generators | **Claude Code** | Needs precise Python async handling. |
| **3. Frontend UI** | React + Canvas + TipTap | **Claude Code** | **Hardest Part**. Save your credits here for pixel-perfect UI. |
| **4. Smart Context** | Python Data Pipelines | **Cursor Pro (GPT-4o)** | Standard data processing tasks. |
| **5. Integration** | Import/Export Scripts | **Antigravity** | Can iterate quickly on file formats. |

**Strategy**:
1.  Use **Antigravity** for architectural "heavy lifting" and initial drafts (Phases 1 & 5).
2.  Use **Claude Code** for the "Masterpiece" UI components (Phase 3) where quality matters most.
3.  Use **Cursor Pro** for quick iteraton and bug fixes (Phase 0, 4).

**For the Duke pilot, Phases 0-4 are REQUIRED. Phase 5 is strongly recommended. Phase 6 is deferred.**
