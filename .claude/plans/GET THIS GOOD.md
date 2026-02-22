# Atlas 2.0 → Atlas 3.0: Agentic MoE & Strict GraphRAG Transformation Plan

## Context

Atlas 2.0 is currently a hybrid RAG system with sequential prompt chains and naive graph extraction. This leads to critical issues:
1. **Severe Graph Hallucinations:** The system hallucinates connections between documents that don't exist, and misses actual connections.
2. **Limited Reasoning:** The "Two-Brain Swarm" is purely sequential. It does not iteratively solve problems, generate hypotheses, or utilize specialized tools effectively.

This plan transforms Atlas into a genuine **Agentic Mixture of Experts (MoE) platform** (inspired by systems like OpenClaw and Microsoft's Magentic-One) backed by an **Evidence-Bound GraphRAG** pipeline. 

**Hard constraint: Everything is free and local-first.** The only paid component is optional AI API tokens (DeepSeek, MiniMax) for heavy reasoning tasks. All libraries are MIT/Apache-2.0, all models run locally, all infrastructure is self-hosted. No SaaS lock-in.

---

# Phase 1: Hybrid LLM Layer (API Model Support)

**Goal**: Let users seamlessly switch between local `.gguf` models and cloud API models (DeepSeek V3/R1, MiniMax 2.5). Agentic workflows requiring rigid tool-calling heavily benefit from API models, while local models handle privacy-sensitive extraction and basic Q&A.

**Key Design Decisions:**
- **LiteLLM Router:** Integrate `litellm` as the universal backend for API calls.
- **Model Registry:** Update `LLMService` to handle `api:deepseek-v3` vs local `deepseek-r1-7b.gguf`.
- **UI:** Implement grouped `<optgroup>` dropdowns (Local / Cloud API) in the frontend.

---

# Phase 2: SOTA GraphRAG - Eliminating Hallucinations

**Problem:** The current `ingest.py` links entities merely if they co-occur in the same chunk. This is the root cause of the "fabricated connections" hallucination.
**Goal:** Upgrade to an evidence-bound, ontology-restricted Graph Extraction pipeline.

### Files to Modify
- `src/backend/app/services/ingest.py`
- `src/backend/app/services/retrieval.py`
- `src/backend/app/services/bm25_index.py` (New)

### Key Design Decisions

#### 1. Strict Ontology & Typed Edges
- Move away from un-typed `CO_OCCURS` edges.
- Define a rigid schema of allowed relationships based on the domain (e.g., `CAUSES`, `INHIBITS`, `CLINICAL_TRIAL_FOR`, `PART_OF`).
- The Extraction LLM must classify relationships strictly into this ontology.

#### 2. Evidence-Bound Extraction (Grounding Constraint)
- The extraction prompt must demand exact string quotes from the source text that justify the edge.
- Example JSON Output:
  ```json
  {
    "source": "Drug X",
    "target": "Pathway Y",
    "type": "INHIBITS",
    "evidence_quote": "Drug X was shown to inhibit Pathway Y by 40%."
  }
  ```

#### 3. Agentic "Critic" Validation Step (Self-Refinement)
- Before committing an edge to the graph, a secondary lightweight validation call (or local Regex check) acts as an Auditor.
- It verifies that the `evidence_quote` is not hallucinated (i.e., it is a direct substring of the chunk). If the exact quote is missing, the edge is instantly dropped.

#### 4. Reciprocal Rank Fusion (RRF) & BM25
- To avoid vector-search drift, integrate `bm25s` for fast sparse (keyword) retrieval.
- Use RRF to fuse BM25 and Vector Search scores: `RRF(d) = SUM(1 / (60 + rank_i(d)))`. Feed the fused results to FlashRank.

---

# Phase 3: Mixture of Experts (MoE) Agentic Architecture

**Goal:** Transition from a rigid prompt chain to a dynamic Multi-Agent "Mixture of Experts" architecture orchestrated via `LangGraph`. This mimics research teams where different agent personas handle specific domains.

### Files to Modify/Create
- `src/backend/app/services/swarm.py` (Rewrite to LangGraph Supervisor architecture)
- `src/backend/app/services/agents/supervisor.py`
- `src/backend/app/services/agents/experts/*.py` (Hypothesis, Writer, Critic)

### The Mixture of Experts (Specialized Personas)
Instead of a monolithic LLM prompt, we instantiate specialized LangGraph nodes (experts):

#### 1. 🧭 The Supervisor (Navigator) Agent
- **Role:** The orchestrator. Analyzes user intent, breaks down complex queries, and delegates sub-tasks to Expert Agents.
- **Workflow:** Routes tasks, aggregates expert outputs, and decides when the research satisfies the user's prompt.

#### 2. 🧠 Hypothesis Generator Expert
- **Role:** Given a broad research question/domain issue, traverses the Knowledge Graph and proposes 3-5 distinct, testable hypotheses.
- **Tools:** `query_graph`, `search_documents`.

#### 3. 🕵️ Information Retrieval Expert
- **Role:** Deep-dives into specific documents to gather evidence proving or disproving a given hypothesis.
- **Tools:** `read_document_section`, `web_search_duckduckgo`, `bm25_search`.

#### 4. ✍️ Paper Writer / Synthesizer Expert
- **Role:** Drafts cohesive research papers, summaries, or domain reports.
- **Constraint:** Operates *strictly* on the structured evidence JSON outputted by the Retrieval Expert. Allowed to write, but not allowed to retrieve.

#### 5. ⚖️ Grounding Auditor (Critic) Expert
- **Role:** Cross-references every claim made by the Paper Writer against the retrieved source chunks.
- **Action:** If a claim is hallucinated/unsupported, it triggers a conditional LangGraph edge forcing the Paper Writer to revise its draft.

---

# Phase 4: Proactive "OpenClaw" Agentic Workflows

**Goal:** Move Atlas beyond reactive Q&A to a proactive research AI that explores document clusters autonomously.

### Key Design Decisions

#### 1. Interactive vs. Autonomous Navigation
- When the Hypothesis Generator creates 5 paths, the workflow pauses.
- **User-in-the-loop (Interactive):** The UI presents the hypotheses; the user clicks which paths the MoE swarm should pursue (human-guided research).
- **Autonomous Mode:** The Supervisor Agent evaluates and pursues the highest-confidence hypothesis entirely in the background.

#### 2. Persistent Workspaces & File Manipulation
- Grant agents access to a sandboxed `/drafts/` filesystem via the LangChain FileManagementToolkit.
- Agents autonomously write intermediate notes, draft documents, and compile bibliographies to disk.
- The UI exposes this as a real-time collaborative workspace where the user watches the agents reason, write drafts, and audit each other in real-time.

---

# Implementation Order & Dependencies

```
Phase 1 (Hybrid LLM Support)    ← Foundational: Must have API model access for reliable MoE tool-calling.
    ↓
Phase 2 (Strict GraphRAG)       ← Eliminates the false connection hallucinations at the data layer.
    ↓
Phase 3 (MoE Architecture)      ← Rebuilds swarm.py into a LangGraph Supervisor + Experts pattern.
    ↓
Phase 4 (Proactive Workflows)   ← Hooks the UI into the multi-agent graph with user-in-the-loop controls.
```

## Tooling & Dependencies Update
| Package | Purpose | License | Needs Install? |
|---------|---------|---------|----------------|
| `litellm>=1.30.0` | Universal API handling | MIT | Yes |
| `bm25s>=0.2.0` | Sparse hybrid retrieval | MIT | Yes |
| `duckduckgo-search` | Web fallback for Retrieval Expert | MIT | Yes |
| `langgraph` | MoE Orchestration | MIT | Installed |
| `flashrank` | Reranking fused search results | Apache 2.0 | Installed |
