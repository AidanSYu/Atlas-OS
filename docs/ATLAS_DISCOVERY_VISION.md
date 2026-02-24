# Atlas — Technical Architecture & Discovery OS Vision

> **"The AI does not know things. It queries a living knowledge substrate… and reasons over it automatically."**

**Version:** 1.0.0 | **Date:** February 2026 | **Status:** Production-Ready Core, Discovery Vision in Design

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Deep-Dive](#2-architecture-deep-dive)
3. [The Knowledge Pipeline](#3-the-knowledge-pipeline)
4. [The Multi-Agent Swarm](#4-the-multi-agent-swarm)
5. [Hardware Optimization & Constraints](#5-hardware-optimization--constraints)
6. [Data Model & Storage](#6-data-model--storage)
7. [Configuration & Extensibility](#7-configuration--extensibility)
8. [The Vision: Discovery OS for Small Molecule & Glycan Research](#8-the-vision-discovery-os-for-small-molecule--glycan-research)
9. [Critical Feasibility Analysis](#9-critical-feasibility-analysis)
10. [Roadmap](#10-roadmap)

---

## 1. System Overview

Atlas is a **standalone Windows desktop application** that constructs a continuous, queryable knowledge layer beneath an AI model. It is not a chatbot—it is a local-first, agentic research operating system.

The application is fully self-contained: no cloud accounts, no external databases, no Docker. A single `.msi` installer bundles the entire stack.

### What Atlas Does Today

| Capability | Implementation |
|---|---|
| **Document Ingestion** | PDF, DOCX, TXT → text extraction → semantic chunking → entity extraction → vector embedding |
| **Hybrid RAG** | Vector search (Qdrant) + BM25 keyword search + Knowledge Graph traversal, fused via Reciprocal Rank Fusion |
| **Multi-Agent Reasoning** | LangGraph-orchestrated swarm with intent routing, reflection loops, and MoE task decomposition |
| **Anti-Hallucination** | Grounding Verifier audits every factual claim against source text with tiered confidence badges |
| **Knowledge Graph** | Rustworkx-backed entity-relationship graph with centrality analysis and subgraph extraction |
| **Local Inference** | `llama-cpp-python` running quantized GGUF models on consumer GPUs (4–8 GB VRAM) |
| **Cloud Hybrid** | Optional API fallback to DeepSeek, MiniMax, OpenAI, or Anthropic via LiteLLM |

---

## 2. Architecture Deep-Dive

### 2.1 Three-Layer Desktop Stack

Atlas is a Tauri desktop app wrapping a Next.js frontend and a Python FastAPI backend. All three run as local processes; no network egress is required.

```mermaid
graph TB
    subgraph TAURI["Tauri Shell - Rust"]
        TW["Window Manager"]
        SP["Sidecar Process Manager"]
    end

    subgraph FRONTEND["Frontend - Next.js 14 + React + TypeScript"]
        CI["ChatInterface.tsx"]
        DAC["DualAgentChat.tsx"]
        GC["GraphCanvas.tsx"]
        FS["FileSidebar.tsx"]
        API["lib/api.ts"]
    end

    subgraph BACKEND["Backend - FastAPI + Python 3.12"]
        RT["routes.py"]
        SW["swarm.py - Agent Orchestrator"]
        RET["retrieval.py - Hybrid RAG"]
        ING["ingest.py - Document Pipeline"]
        LLM["llm.py - Hybrid LLM Service"]
        GR["graph.py - Graph Queries"]
    end

    subgraph DATA["Data Layer"]
        QD["Qdrant - Vector Store"]
        SQ["SQLite - Relational Store"]
        RW["Rustworkx - Graph Engine"]
    end

    TW --> CI
    SP --> RT
    CI --> API
    DAC --> API
    GC --> API
    FS --> API
    API -->|HTTP :8000| RT
    RT --> SW
    RT --> RET
    RT --> ING
    RT --> GR
    SW --> LLM
    RET --> QD
    RET --> SQ
    GR --> RW
    GR --> SQ
    ING --> QD
    ING --> SQ
    ING --> RW
```

### 2.2 Key File Map

| Layer | File | Purpose | Size |
|---|---|---|---|
| Backend Core | `src/backend/app/services/swarm.py` | Full agent orchestration: Navigator, Navigator 2.0, Cortex, routing | 2,787 lines |
| Backend Core | `src/backend/app/services/llm.py` | Hybrid LLM: local GGUF + cloud API via LiteLLM, CUDA DLL management | 1,116 lines |
| Backend Core | `src/backend/app/services/retrieval.py` | Hybrid RAG: vector + BM25 + graph, Reciprocal Rank Fusion | 494 lines |
| Backend Core | `src/backend/app/services/ingest.py` | Document pipeline: extraction → chunking → GLiNER NER → embedding | 1,190 lines |
| Agents | `src/backend/app/services/agents/meta_router.py` | Intent classification (SIMPLE/DEEP/BROAD/MULTI_STEP) + model swapping | 101 lines |
| Agents | `src/backend/app/services/agents/librarian.py` | Fast 2-node graph: Retrieve → Answer. Handles ~80% of queries in <5s | 216 lines |
| Agents | `src/backend/app/services/agents/supervisor.py` | MoE Supervisor: decomposes queries, delegates to experts, audits drafts | 372 lines |
| Agents | `src/backend/app/services/agents/grounding.py` | Anti-hallucination: extracts claims → verifies each against source text | 161 lines |
| Experts | `src/backend/app/services/agents/experts/hypothesis.py` | Generates ranked hypotheses from evidence | — |
| Experts | `src/backend/app/services/agents/experts/retrieval_expert.py` | Targeted evidence gathering per sub-task | — |
| Experts | `src/backend/app/services/agents/experts/writer.py` | Drafts cited research prose from evidence | — |
| Experts | `src/backend/app/services/agents/experts/critic.py` | Reviews and critiques drafts for logical gaps | — |
| Config | `src/backend/app/core/config.py` | 50+ tunable parameters (reflection iterations, chunk sizes, MoE rounds, etc.) | 129 lines |
| Database | `src/backend/app/core/database.py` | SQLAlchemy ORM: Project, Document, DocumentChunk, Node, Edge | 266 lines |

---

## 3. The Knowledge Pipeline

When a user uploads a document, Atlas runs a multi-stage ingestion pipeline defined in `ingest.py`:

```mermaid
graph LR
    A["PDF / DOCX / TXT"] --> B["Text Extraction"]
    B --> C["Semantic Chunking"]
    C --> D["GLiNER NER"]
    C --> E["Nomic Embed v1.5"]
    D --> F["SQLite Nodes and Edges"]
    D --> G["Rustworkx Graph"]
    E --> H["Qdrant Vectors"]
    C --> I["BM25 Index"]
    C --> J["RAPTOR Summaries"]
```

**Key implementation details:**

- **Text Extraction:** Tries Docling VLM first for structure-preserving extraction (tables, charts), falls back to `pdfplumber`/`PyPDF` (`_extract_pdf_text` in `ingest.py`)
- **Chunking:** Uses semantic chunking via `semantic_chunker.py` (target: 512 tokens), falls back to fixed-size overlap (1000 chars, 200 overlap)
- **Entity Extraction:** GLiNER (`gliner_small-v2.1`, ~50 MB) extracts typed entities (PERSON, ORGANIZATION, CONCEPT, etc.) without requiring an LLM call, via `_extract_entities_gliner`
- **RAPTOR:** `raptor.py` generates hierarchical cluster summaries (L1 clusters) for each document, enabling multi-resolution retrieval
- **BM25:** `bm25_index.py` maintains a sparse keyword index fused with vector results via Reciprocal Rank Fusion (`rrf_fuse`)

---

## 4. The Multi-Agent Swarm

The core intelligence lives in `swarm.py` (2,787 lines), orchestrated via LangGraph `StateGraph` objects.

### 4.1 Query Routing

```mermaid
flowchart TD
    Q["User Query"] --> MR["Meta-Router"]
    MR -->|SIMPLE| LIB["Librarian - Fast vector lookup - 2 nodes, ~5s"]
    MR -->|DEEP_DISCOVERY| NAV["Navigator 2.0 - Multi-turn reflection - 5 nodes, ~30-60s"]
    MR -->|BROAD_RESEARCH| CTX["Cortex MoE - Task decomposition - 6+ nodes, ~60-120s"]
    MR -->|MULTI_STEP| BOTH["Navigator + Cortex Sequential pipeline"]

    LIB --> ANS["Synthesized Answer + Confidence Score + Citations"]
    NAV --> ANS
    CTX --> ANS
    BOTH --> ANS
```

The `Meta-Router` (`meta_router.py`) classifies each query using a zero-shot LLM classification prompt and also performs **dynamic model swapping** — selecting faster 3B models for simple queries and larger 7B–8B models for deep discovery tasks via `ensure_optimal_model`.

### 4.2 Librarian Agent (Fast Path)

Defined in `librarian.py`. A minimal 2-node LangGraph:

```
retrieve_node → answer_node → END
```

- **Retrieve:** Vector search via Qdrant `query_points` → optional FlashRank reranking → cosine threshold filtering (≥0.4 for vector, ≥0.05 for reranked)
- **Answer:** Single LLM call with XML-structured output (`<reasoning>`, `<confidence>`, `<answer>` tags)
- Handles **~80% of queries** in under 5 seconds

### 4.3 Navigator 2.0 (Deep Discovery with Reflection)

The Navigator implements multi-turn reflection loops (up to `MAX_REFLECTION_ITERATIONS=3`). Its LangGraph contains 5 nodes:

```mermaid
flowchart TD
    P["Planner Node"] --> R["Retriever Node"]
    R --> RE["Reasoner Node"]
    RE --> CR["Critic Node"]
    CR -->|PASS or iteration >= 3| F["Final Answer + Evidence Map"]
    CR -->|REVISE gaps exist| P
```

**State tracked per iteration** (from `NavigatorState` in `swarm.py`):
- `reasoning_plan`, `identified_gaps`, `search_terms` — The Planner's output
- `graph_summary` — Rustworkx subgraph centrality analysis
- `accumulated_evidence` — Grows across reflection iterations
- `confidence_score` — Auto-passes at ≥0.75 threshold (`NAVIGATOR_CONFIDENCE_THRESHOLD`)
- `iteration_count` — Capped at 3 to prevent infinite loops

### 4.4 Cortex MoE (Mixture of Experts)

For broad research queries, the Cortex decomposes the question into sub-tasks and delegates to specialized experts. Built in `supervisor.py`:

```mermaid
flowchart TD
    SUP["Supervisor - Decomposes query"] --> HYP["Hypothesis Expert"]
    HYP --> RET["Retrieval Expert"]
    RET --> WRT["Writer Expert"]
    WRT --> AUD["Grounding Auditor"]
    AUD -->|PASS| SYN["Supervisor Synthesize"]
    AUD -->|FAIL round < max| RET
```

**MoE State** (`MoEState` in `supervisor.py`) tracks:
- `sub_tasks` — Decomposed sub-queries (default: 5 via `CORTEX_NUM_SUBTASKS`)
- `hypotheses` and `selected_hypothesis` — Ranked by the Hypothesis Expert
- `draft` and `draft_version` — Iterative drafting by the Writer Expert
- `grounding_results`, `ungrounded_claims`, `audit_verdict` — From the Grounding Auditor
- `max_rounds` — Capped at 5 (`MOE_MAX_EXPERT_ROUNDS`)

### 4.5 Grounding Verifier (Anti-Hallucination)

Defined in `grounding.py`. Every factual claim in an agent's output is individually checked:

1. **Claim Extraction:** LLM call decomposes the answer into numbered factual claims
2. **Per-Claim Verification:** Each claim is embedded and searched against Qdrant; cosine similarity determines badge level:
   - `GROUNDED` (score > 0.82) — Directly supported by cited source
   - `SUPPORTED` (0.72–0.82) — Paraphrased but source matches
   - `INFERRED` (0.60–0.72) — Synthesis/inference, not verbatim in source
   - `UNVERIFIED` (< 0.60) — No matching source found
3. **Overall Score:** Percentage of claims that are `GROUNDED` or `SUPPORTED`

---

## 5. Hardware Optimization & Constraints

Atlas targets the **NVIDIA RTX 3050 (4 GB VRAM)** as the minimum hardware. Every architectural decision flows from this constraint:

| Technique | Implementation | Why it Matters |
|---|---|---|
| **Sequential Agent Execution** | LangGraph nodes run serially | Only one LLM inference at a time; never exceeds VRAM |
| **GBNF Grammar Constraints** | `generate_with_validation` in `swarm.py` | Forces small 3B–7B models to output valid JSON/XML without fine-tuning |
| **Dynamic Model Swapping** | `ensure_optimal_model` in `meta_router.py` | Uses fast 3B models for simple queries, 7B+ for complex ones |
| **Partial GPU Offload** | `DEFAULT_GPU_LAYERS = 35` in `llm.py` | Offloads ~3.2 GB to GPU, keeps rest in RAM; tunable via env var |
| **GLiNER NER** | `_extract_entities_gliner` in `ingest.py` | ~50x faster than LLM-based extraction, ~50 MB model footprint |
| **Rustworkx over NetworkX** | `get_rustworkx_subgraph` in `graph.py` | C/Rust graph math is orders of magnitude faster than pure Python |
| **Embedded Qdrant** | In-process path mode (no separate server) | Zero network overhead, single-process memory management |
| **Prompt Templates** | `prompt_templates.py` (750 lines) | Few-shot examples tuned per node reduce hallucination in small models |

### LLM Configuration (from `config.py`):
```
LLM_CONTEXT_SIZE    = 8192    # 8K context window (4096 for 3B if OOM)
LLM_N_BATCH         = 512     # Batch size for prompt processing
LLM_USE_MLOCK       = True    # Pin model weights in RAM
DEFAULT_GPU_LAYERS   = 35     # Partial VRAM offload
```

---

## 6. Data Model & Storage

All persistence is defined in `database.py`:

```mermaid
erDiagram
    Project ||--o{ Document : contains
    Project ||--o{ Node : scopes
    Project ||--o{ Edge : scopes
    Document ||--o{ DocumentChunk : splits_into
    Document ||--o{ Node : extracted_from
    Document ||--o{ Edge : extracted_from
    Node ||--o{ Edge : source_of
    Node ||--o{ Edge : target_of

    Project {
        string id PK
        string name UK
        string description
        datetime created_at
    }
    Document {
        string id PK
        string filename
        string file_type
        string mime_type
        string file_hash
        integer file_size
        string status
        string project_id FK
    }
    DocumentChunk {
        string id PK
        string document_id FK
        integer chunk_index
        string text
        integer page_number
        json chunk_metadata
    }
    Node {
        string id PK
        string label
        string entity_type
        json properties
        string document_id FK
        string project_id FK
    }
    Edge {
        string id PK
        string source_id FK
        string target_id FK
        string type
        float weight
        json properties
        string document_id FK
        string project_id FK
    }
```

**Key indexes** (performance-critical):
- `idx_nodes_label` — Fast entity lookup by type
- `idx_edges_source_target` — Graph traversal queries
- `idx_documents_file_hash` — Deduplication on upload
- `idx_chunk_document` — Chunk retrieval by document

**Graph edge ontology** (from `GRAPH_ONTOLOGY_EDGE_TYPES` in config):
```
CAUSES, INHIBITS, ENABLES, PART_OF, RELATED_TO, CONTRADICTS,
SUPPORTS, CLINICAL_TRIAL_FOR, TREATS, DIAGNOSES, MEASURED_BY,
AUTHORED_BY, PUBLISHED_IN, FUNDED_BY
```

> **Note:** The edge types `CLINICAL_TRIAL_FOR`, `TREATS`, and `DIAGNOSES` are already built into the ontology — the codebase was designed with biomedical discovery in mind from day one.

---

## 7. Configuration & Extensibility

All 50+ parameters are defined in a single `Settings` class in `config.py`, loaded from `.env`:

| Category | Parameters | Defaults |
|---|---|---|
| **Navigator Reflection** | `ENABLE_NAVIGATOR_REFLECTION`, `MAX_REFLECTION_ITERATIONS`, `NAVIGATOR_CONFIDENCE_THRESHOLD` | `True`, `3`, `0.75` |
| **Cortex MoE** | `ENABLE_CORTEX_CROSSCHECK`, `CORTEX_NUM_SUBTASKS`, `MOE_MAX_EXPERT_ROUNDS`, `MOE_HYPOTHESIS_COUNT` | `True`, `5`, `5`, `3` |
| **RAG Pipeline** | `ENABLE_RERANKING`, `RERANK_TOP_N`, `USE_SEMANTIC_CHUNKING`, `USE_RAPTOR` | `True`, `5`, `True`, `True` |
| **Document Parsing** | `USE_DOCLING`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `SEMANTIC_CHUNK_TOKENS` | `True`, `1000`, `200`, `512` |
| **Graph** | `ENABLE_EVIDENCE_BOUND_EXTRACTION`, `ENABLE_GRAPH_CRITIC`, `GRAPH_CACHE_TTL` | `True`, `True`, `300s` |
| **Cloud Models** | `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Empty (local-only) |

---

## 8. The Vision: Discovery OS for Small Molecule & Glycan Research

### 8.1 The Core Idea

Atlas today is a generalized research OS. The vision is to vertically integrate it into a **closed-loop drug discovery platform** — starting with one specific, high-value domain: **small molecule and glycan discovery**.

The philosophy: **Atlas is not a tool. It is an Operating System.**

Just as Windows provides the kernel and UI while third-party "apps" provide specialized functionality, Atlas provides the knowledge substrate, agent orchestration, and UI — while specialized **discovery apps** (retrosynthesis engines, NMR interpreters, assay analyzers) are plugged in as modular agents.

### 8.2 The Closed-Loop Discovery Workflow

```mermaid
flowchart TB
    subgraph P1["Phase 1: Hit Identification"]
        A["Researcher defines target and goals"] --> B["Predictive Model App - DECL, ChemProp"]
        B --> C["AI Agent filters and ranks hit compounds"]
    end

    subgraph P2["Phase 2: Structure Design and Synthesis"]
        C --> D["Generative Chemistry Agent"]
        D --> E["Retrosynthesis Engine App"]
        E --> F["Researcher performs synthesis in lab"]
        F -->|Step failed| E
    end

    subgraph P3["Phase 3: Verification"]
        F --> G["Upload raw NMR / Mass Spec data"]
        G --> H["Spectroscopy Agent interprets NMR/MS"]
        H -->|Match| I["Verified Molecule"]
        H -->|Mismatch| E
    end

    subgraph P4["Phase 4: Biological Testing"]
        I --> J["Biological Assay Agent"]
        J --> K{Efficacy Threshold?}
        K -->|Pass| L["Candidate Pool"]
        K -->|Fail| D
    end

    subgraph P5["Phase 5: Clinical Readiness"]
        L --> M["Regulatory Agent - FDA, scalability"]
        M --> N["Clinical Trial Matcher"]
    end
```

### 8.3 Why Glycans Are the "Killer App"

| Molecule Class | Synthesis Automation | Atlas Opportunity |
|---|---|---|
| **Peptides** | Highly automated (SPPS machines) | Low — already solved |
| **Nucleic Acids** | Highly automated (phosphoramidite chemistry) | Low — already solved |
| **Small Molecules** | Semi-automated (HTS + medicinal chemistry) | Medium — AI can accelerate design |
| **Glycans** | Essentially manual; no universal template | **Extremely High** — unsolved problem |

Glycans are critical in biological signaling, immune response, and disease markers — but their synthesis is prohibitively difficult due to:
- **Non-linear branching** (unlike the linear chains of peptides/DNA)
- **Complex stereochemistry** (anomeric configurations: α vs β glycosidic bonds)
- **Protecting group orchestration** (dozens of orthogonal protection strategies)

> A researcher can spend **1–2 years synthesizing a single glycan molecule.** If Atlas can reliably predict retrosynthesis pathways for glycans, it is an immediate, fundamental breakthrough in biochemistry.

### 8.4 The Plugin Architecture

```mermaid
graph TB
    subgraph KERNEL["Atlas OS Kernel"]
        K1["Agent Orchestrator - LangGraph Swarm"]
        K2["Knowledge Substrate - Qdrant + Rustworkx + SQLite"]
        K3["LLM Service - Local + Cloud Hybrid"]
        K4["Grounding Verifier"]
    end

    subgraph PLUGINS["Discovery Apps - Plugins"]
        P1["Retrosynthesis Engine"]
        P2["NMR/MS Interpreter"]
        P3["Biological Assay Analyzer"]
        P4["FDA Regulatory Checker"]
        P5["Clinical Trial Matcher"]
        P6["DECL/ChemProp Connector"]
    end

    subgraph THIRD["Future Third-Party Apps"]
        T1["Lab X: Custom QSAR Predictor"]
        T2["Lab Y: Glycan Pathway DB"]
        T3["Lab Z: Cell Line Screener"]
    end

    K1 --> P1
    K1 --> P2
    K1 --> P3
    K1 --> P4
    K1 --> P5
    K1 --> P6
    K1 --> T1
    K1 --> T2
    K1 --> T3
    K2 --> K1
    K3 --> K1
    K4 --> K1
```

> **Important:** The plugin system is the fundamental differentiator from Recursion, Schrodinger, and BenevolentAI — all of which are closed, vertically integrated pipelines. Atlas is the **open, local-first OS** where labs keep their IP entirely on their own machines.

---

## 9. Competitive Landscape, Moat, and Strategy

### 9.1 Competitor Analysis

The AI-for-science space is heavily funded but fragmented. Every competitor solves one slice of the R&D pipeline — none provides an open OS layer.

| Company | Funding | What They Do | Weakness Atlas Exploits |
|---|---|---|---|
| **Recursion Pharmaceuticals** | $1.5B+ raised, public (RXRX) | Closed-loop phenomics + ML drug discovery | Fully closed platform. Your data is their data. No plugin system. Only accessible to $B pharma budgets. |
| **Schrödinger** | Public (SDGR), $600M+ rev | Physics-based molecular simulation + ML | Licensing model ($100K+/yr per seat). Black-box solvers. No agentic AI, no knowledge graph. |
| **Insilico Medicine** | $400M+ raised | End-to-end AI drug discovery (target ID to clinical) | Proprietary pipeline — you use their targets, their chemistry. No local deployment. |
| **BenevolentAI** | Public (BAI), $400M+ raised | Knowledge graph for target discovery | Knowledge graph only — no synthesis planning, no NMR verification, no closed-loop feedback. |
| **Relay Therapeutics** | $700M+ raised | Motion-based drug design (protein dynamics) | Narrow focus on protein motion. No OS layer, no generalized R&D capability. |
| **PostEra** | $26M raised | ML for medicinal chemistry (Manifold platform) | Chemistry-only. No document intelligence, no knowledge graph, no multi-agent reasoning. |
| **Chemify** | $60M raised (Lee Cronin) | Automated chemical synthesis via "chemputation" | Hardware-dependent. Requires their proprietary robots. Not software-first. |
| **Benchling** | $6.1B valuation | Lab informatics and data management (ELN/LIMS) | Pure data management — zero AI reasoning. No synthesis planning. No agent intelligence. |

**The gap in the market:** Every competitor above is either (a) a closed vertical pipeline you rent, or (b) a point solution for one step. **Nobody is building the open OS that connects all these steps with agentic intelligence.**

### 9.2 Why "Zero Lock-in" Is Not the Moat

Let's be honest: "your data stays local" and "zero lock-in" sound good in a pitch deck, but they are **not defensible**. Any competitor can claim the same thing tomorrow. If the only reason someone uses Atlas is that it's open, they'll leave the moment a closed product is 10% better.

The real question: **What makes Atlas impossible to leave once you're in?**

### 9.3 The Actual Moat: Compound Intelligence

Atlas wins by building three compounding advantages that get stronger with every user and every experiment:

**Moat 1: The Data Flywheel (Synthesis Memory)**

Every time a researcher uses Atlas to plan a synthesis and reports back what worked and what failed, that data trains the local retrosynthesis model. Over time, each lab's Atlas instance becomes a deeply personalized expert on *their specific chemistry*. 

- A lab that has used Atlas for 2 years has 2 years of synthesis memory that no competitor can replicate.
- This is not transferable — it's embedded in their local knowledge graph.
- Switching to a competitor means starting from zero.

This is lock-in through *accumulated intelligence*, not through data hostage-taking.

**Moat 2: The Plugin Ecosystem (App Store Effect)**

If the best retrosynthesis plugin, the best NMR interpreter, and the best assay analyzer all run on Atlas, then leaving Atlas means losing access to those tools. This is the iOS/Android playbook:

- Apple doesn't lock you in by holding your photos hostage.
- Apple locks you in because the best apps are only on iOS.

Atlas's open plugin SDK is not a weakness — it's the mechanism that creates ecosystem lock-in. The more third-party tools built for Atlas, the harder it is to leave.

**Moat 3: The Glycan Wedge (Domain Credibility)**

Glycan synthesis is the single hardest unsolved problem in synthetic chemistry. If Atlas cracks it first — even partially — it earns instant, permanent credibility as the serious platform for hard chemistry. Every pharma company exploring glycan therapeutics (and there are many, because glycans are involved in cancer, autoimmune disease, and viral defense) will come to Atlas because nobody else has a working solution.

This is "Intel Inside" for chemistry: you don't switch away from the platform that solved the thing nobody else could.

### 9.4 Total Addressable Market: Beyond Pharma

Targeting only biotech labs keeps Atlas small. But the predict → synthesize → verify → iterate loop is universal across all R&D:

| Industry | R&D Spend (Global) | How Atlas Applies |
|---|---|---|
| **Pharmaceuticals** | $250B/yr | Drug discovery, glycan therapeutics, biologics |
| **Materials Science** | $50B/yr | Polymer design, catalyst discovery, alloy optimization |
| **Agricultural Chemistry** | $15B/yr | Pesticide/herbicide design, crop protection molecules |
| **Battery and Energy** | $30B/yr | Electrolyte design, solid-state materials, catalyst screening |
| **Specialty Chemicals** | $40B/yr | Fragrance/flavor molecules, industrial coatings, adhesives |
| **Academic Research** | $700B/yr (all fields) | Any lab doing experimental research with documents and data |

The total addressable market is not "biotech startups" — it's **every organization on Earth that does experimental R&D** (~$1T/yr). Atlas starts with pharma (highest pain, highest willingness to pay) and expands horizontally as the plugin ecosystem matures.

### 9.5 How Atlas Wins: The Playbook

```mermaid
flowchart LR
    subgraph YEAR1["Year 1: Wedge"]
        W1["Crack glycan retrosynthesis"] --> W2["First 10 pharma lab users"]
        W2 --> W3["Prove the closed-loop works"]
    end

    subgraph YEAR2["Year 2: Ecosystem"]
        W3 --> E1["Open plugin SDK"]
        E1 --> E2["Third-party tools built on Atlas"]
        E2 --> E3["Network effects compound"]
    end

    subgraph YEAR3["Year 3: Platform"]
        E3 --> P1["Expand to materials, ag-chem, energy"]
        P1 --> P2["Atlas becomes the R&D OS standard"]
        P2 --> P3["Revenue from enterprise licenses + plugin marketplace"]
    end
```

**The sequence matters:**

1. **Win the hardest problem first** (glycan synthesis) — this earns credibility that no amount of marketing can buy
2. **Build the ecosystem** (plugin SDK) — this creates switching costs that compound over time  
3. **Expand horizontally** (materials, ag-chem, energy) — the OS layer generalizes, only the plugins change
4. **Monetize the platform** (enterprise licenses + plugin marketplace commission) — this is a $B revenue model, not a $M one

### 9.6 Feasibility Check: Algorithms and Robotics

**Are current prediction algorithms good enough for AI to leverage?**

| Algorithm Type | Maturity | Atlas Strategy |
|---|---|---|
| **Property Prediction** (ChemProp, ADMET) | Production-ready | Wrap as plugin; AI agent invokes via API |
| **Structure Prediction** (AlphaFold 3, RoseTTAFold) | Production-ready for proteins | Integrate for target validation |
| **Retrosynthesis** (AiZynthFinder, ASKCOS) | Good for simple molecules, weak on stereochemistry | Starting point — **the human feedback loop is the differentiator** |
| **NMR Prediction** (nmrshiftdb2) | Databases exist; AI interpretation is nascent | Train an NMR comparison agent |
| **Glycan Pathways** | Open-source is minimal | **The gap Atlas fills** — researcher-in-the-loop from day one |

**Can robots handle synthesis?**

| Task | Robotic Readiness | Atlas Strategy |
|---|---|---|
| **High-Throughput Screening** | Mature (Opentrons, Hamilton) | Integrate plate reader data as input app |
| **Organic Synthesis** | Extremely difficult to roboticize | **Keep human-driven.** Atlas is the brain, the researcher is the hands |
| **Automated Flow Chemistry** (ChemSpeed) | Specialized, expensive | Long-term integration target (Year 2+) |

> **Key insight:** Atlas's value is in the **informational bottleneck**, not the physical one. Design the pathway, interpret the NMR, decide what to screen next — these cognitive tasks are where AI creates 100x leverage. The wet lab stays human for now.

---

## 10. Roadmap

### For a16z / YC Delivery

```mermaid
gantt
    title Atlas Discovery OS Roadmap
    dateFormat YYYY-MM
    axisFormat %b %Y

    section Phase 1 Plugin Infrastructure
    App plugin architecture design     :p1a, 2026-03, 2026-04
    Non-text data ingestion            :p1b, 2026-04, 2026-05
    Plugin SDK and API contract        :p1c, 2026-04, 2026-06

    section Phase 2 Retrosynthesis Copilot
    Integrate AiZynthFinder            :p2a, 2026-06, 2026-07
    Synthesis Feedback Loop agent      :p2b, 2026-06, 2026-08
    Glycan stereochemistry tuning      :p2c, 2026-07, 2026-09

    section Phase 3 Verification Engine
    NMR spectra prediction agent       :p3a, 2026-09, 2026-11
    NMR MS comparison and confidence   :p3b, 2026-10, 2026-12

    section Phase 4 Closed Pipeline
    Biological assay feedback loop     :p4a, 2027-01, 2027-03
    ClinicalTrials and FDA connectors  :p4b, 2027-02, 2027-06

    section Phase 5 Platform Release
    Third-party plugin SDK beta        :p5a, 2027-06, 2027-09
    Lab partnership program            :p5b, 2027-06, 2027-12
```

### Phase Details

| Phase | Timeline | Deliverables | Success Criteria |
|---|---|---|---|
| **1: Plugin Infrastructure** | Months 1–3 | App architecture, non-text data ingestion (NMR formats: JCAMP-DX, Bruker), Plugin SDK | A third-party Python script can register as an Atlas app and be invoked by the agent swarm |
| **2: Retrosynthesis Copilot** | Months 3–6 | AiZynthFinder integration, Synthesis Feedback Loop, glycan stereochemistry fine-tuning | Researcher inputs a failed step, agent recalculates pathway within 60 seconds |
| **3: Verification Engine** | Months 6–9 | NMR spectra predictor, NMR/MS comparison agent with confidence scoring | AI outputs "85% match to target glycan, 15% chance stereoisomer" from raw NMR data |
| **4: Closed Pipeline** | Months 9–15 | Biological assay feedback loop, ClinicalTrials.gov and FDA regulatory connectors | End-to-end: hit to design to synthesis to verify to assay to regulatory check with zero manual data transfer |
| **5: Platform Release** | Year 2+ | Public plugin SDK, lab partnership program, ecosystem growth | External labs building and publishing their own Atlas apps |

---

> *"Atlas is not another AI tool. It is the operating system for scientific discovery — starting with the hardest molecule class on Earth."*
