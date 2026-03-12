# Atlas — Complete Codebase Reference

> **Purpose**: Give any AI full understanding of this codebase without reading source files.
> **Stack**: Tauri (Rust) + FastAPI (Python) + Next.js 14 (TypeScript)
> **What it does**: Desktop research tool that ingests PDFs, builds knowledge graphs, and answers questions via multi-agent RAG with local/cloud LLMs.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Tauri Shell (Rust)                    │
│  src/tauri/src/main.rs — sidecar mgmt, window, CSP     │
├─────────────────────────────────────────────────────────┤
│           Next.js 14 Frontend (TypeScript)               │
│  Port 3001 — Zustand stores, SSE streaming, Tailwind    │
├─────────────────────────────────────────────────────────┤
│            FastAPI Backend (Python)                       │
│  Port 8000 — LLM, RAG, knowledge graph, plugins         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ SQLite   │ │ Qdrant   │ │ GLiNER   │ │ llama-cpp  │ │
│  │ (schema) │ │ (vectors)│ │ (NER)    │ │ (local LLM)│ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Data flow**: Upload PDF → pdfplumber extracts text → chunked (1000 tokens, 200 overlap) → embedded (nomic-embed-text-v1.5, 768d) → stored in Qdrant + SQLite → GLiNER extracts entities → knowledge graph nodes/edges in SQLite → user queries → hybrid RAG retrieval → LLM generates answer with citations.

**Discovery OS Golden Path** (7-stage research loop):
```
Stage 1: PRIME          → Mission Control modal (corpus + target params)
Stage 2: GENERATE       → LLM proposes candidate structures
Stage 3: SCREEN         → Deterministic ML property screening
Stage 4: SURFACE        → Candidate Artifact cards with approve/reject
Stage 5: SYNTHESIS_PLAN → Retrosynthesis route planning
Stage 6: SPECTROSCOPY   → NMR/XRD validation vs predicted spectra
Stage 7: FEEDBACK       → Experimental results → knowledge graph → Stage 2
```

**Branching Epoch Model**: Research is non-linear. Each "fork" creates a new Epoch with inherited parameters. Users can run parallel experiments, compare branches, and switch between Epochs freely.

---

## 2. File Structure

```
Project Root
├── config/                    # .env, aider config
├── installers/                # Built .exe/.msi outputs
├── scripts/
│   ├── build/build-backend.ps1   # PyInstaller (incremental)
│   ├── dev/run_backend.ps1       # Dev server launcher
│   └── setup/setup-prereqs.ps1   # Pip install with backtracking fix
├── src/
│   ├── backend/               # Python backend
│   │   ├── app/
│   │   │   ├── main.py              # FastAPI app, startup, CORS, GZip
│   │   │   ├── api/routes.py        # ALL endpoints (~1000 lines)
│   │   │   ├── core/
│   │   │   │   ├── config.py        # Settings singleton (50+ vars)
│   │   │   │   ├── database.py      # SQLAlchemy models + SQLite
│   │   │   │   └── memory.py        # LangGraph MemorySaver singleton
│   │   │   └── services/
│   │   │       ├── llm.py           # LLM service (llama-cpp + LiteLLM)
│   │   │       ├── swarm.py         # Two-brain LangGraph (Navigator + Cortex)
│   │   │       ├── retrieval.py     # Hybrid RAG (vector+BM25+graph+rerank)
│   │   │       ├── ingest.py        # PDF→chunks→vectors→entities
│   │   │       ├── graph.py         # NetworkX queries
│   │   │       ├── meta_router.py   # Intent classifier
│   │   │       ├── moe.py           # Mixture of Experts pipeline
│   │   │       ├── plugins/         # Discovery OS plugin system
│   │   │       │   ├── base.py             # BasePlugin ABC
│   │   │       │   ├── __init__.py         # PluginManager singleton
│   │   │       │   ├── property_predictor.py  # RDKit MW/LogP/QED
│   │   │       │   ├── toxicity_checker.py    # SMARTS/PAINS screening
│   │   │       │   └── spectrum_verifier.py   # NMR .jdx analysis
│   │   │       └── agents/
│   │   │           ├── discovery_graph.py  # ReAct LangGraph
│   │   │           ├── discovery_state.py  # DiscoveryState TypedDict
│   │   │           └── tool_schemas.py     # Tool I/O schemas
│   │   ├── models/                # GGUF models, embeddings, NER
│   │   ├── run_server.py          # Canonical entry point
│   │   └── atlas.spec             # PyInstaller spec
│   ├── frontend/              # Next.js 14
│   │   ├── app/
│   │   │   ├── layout.tsx           # Root: Inter + Sora + IBM Plex Mono
│   │   │   ├── globals.css          # Dark void theme (#070A0E)
│   │   │   ├── page.tsx             # Projects dashboard
│   │   │   └── project/
│   │   │       ├── [id]/page.tsx    # Dynamic project loader
│   │   │       └── workspace-page.tsx # Main 3-pane workspace
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatShell.tsx         # Container: mode tabs, auto-routing, submission
│   │   │   │   ├── ConversationView.tsx  # Messages, generative UI, follow-up pills
│   │   │   │   ├── CommandSurface.tsx    # Input area, routing badge, mode override
│   │   │   │   ├── RunProgressDisplay.tsx # Streaming telemetry card
│   │   │   │   ├── RunErrorDisplay.tsx   # Error taxonomy + retry
│   │   │   │   ├── RunAuditPanel.tsx     # Slide-over run history + event timeline
│   │   │   │   └── index.ts             # Re-exports
│   │   │   ├── discovery/              # Discovery OS Golden Path components
│   │   │   │   ├── CandidateArtifact.tsx    # Stage 4: Candidate cards with approve/reject
│   │   │   │   ├── SpectroscopyArtifact.tsx # Stage 6: NMR/XRD validation display
│   │   │   │   └── BioassayFeedbackForm.tsx # Stage 7: Experimental result submission
│   │   │   ├── generative/
│   │   │   │   ├── CitationCard.tsx      # Citation with relevance bar
│   │   │   │   ├── ComparisonTable.tsx   # Markdown table renderer
│   │   │   │   └── MetricCard.tsx        # Extracted metric display
│   │   │   ├── OmniBar.tsx          # Ctrl+K command palette + query submission
│   │   │   ├── DualAgentChat.tsx    # Thin shim → re-exports ChatShell
│   │   │   ├── PDFViewer.tsx        # PDF display + "Ask about page"
│   │   │   ├── TextViewer.tsx       # .txt/.md/.csv/.json viewer
│   │   │   ├── KnowledgeGraph.tsx   # @xyflow/react + d3-force graph
│   │   │   ├── EditorPane.tsx       # TipTap WYSIWYG editor
│   │   │   ├── ContextEngine.tsx    # Smart reading suggestions
│   │   │   ├── AgentWorkbench.tsx   # Swarm/MoE progress side panel
│   │   │   ├── DiscoveryWorkbench.tsx # Chemistry ReAct terminal
│   │   │   ├── ResearchCanvas.tsx   # Spatial research board
│   │   │   ├── LibrarySidebar.tsx   # Document upload + file list
│   │   │   ├── SettingsModal.tsx    # API keys, model config
│   │   │   └── WelcomeTour.tsx      # First-time onboarding
│   │   ├── stores/
│   │   │   ├── chatStore.ts         # Per-mode message arrays (Zustand + persist)
│   │   │   ├── runStore.ts          # Run audit history (Zustand + IndexedDB)
│   │   │   ├── graphStore.ts        # Knowledge graph state
│   │   │   ├── discoveryStore.ts    # Discovery OS Golden Path state (Epochs, stages)
│   │   │   └── toastStore.ts        # Global notifications
│   │   ├── hooks/
│   │   │   ├── useRunManager.ts     # Streaming orchestration hook
│   │   │   └── useContextEngine.ts  # Context suggestions hook
│   │   ├── lib/
│   │   │   ├── api.ts               # API client (all endpoints + types)
│   │   │   ├── discovery-types.ts   # Discovery OS Golden Path type definitions
│   │   │   ├── stream-adapter.ts    # Unified SSE parser + NormalizedEvent
│   │   │   ├── design-system/motion.ts # Spring + animation configs
│   │   │   └── utils.ts             # cn() helper (clsx + tailwind-merge)
│   │   ├── tailwind.config.js       # Custom colors, fonts, animations
│   │   └── package.json             # Dependencies
│   └── tauri/
│       ├── tauri.conf.json          # Window, sidecar, CSP, bundle
│       └── src/main.rs              # Rust sidecar management
└── tests/                     # Test suites
```

---

## 3. Database Schema (SQLite)

5 tables with foreign keys enforced, WAL mode, normal sync:

```
projects
  id: String PK (UUID)
  name: String UNIQUE NOT NULL
  description: Text
  created_at, updated_at: DateTime

documents
  id: String PK (UUID)
  filename: String NOT NULL
  file_hash: String INDEXED (SHA256 dedup)
  file_path, file_size, mime_type
  project_id: FK → projects.id INDEXED
  status: String ("pending" | "processing" | "completed" | "failed")
  total_chunks, processed_chunks: Integer
  doc_metadata: JSON
  uploaded_at, processed_at: DateTime

document_chunks
  id: String PK (UUID)
  document_id: FK → documents.id INDEXED NOT NULL
  text: Text NOT NULL
  chunk_index: Integer
  page_number: Integer
  start_char, end_char: Integer
  chunk_metadata: JSON
  INDEX(document_id, chunk_index)

nodes (Knowledge Graph Entities)
  id: String PK (UUID)
  label: String INDEXED ("chemical", "protein", "disease", "concept", etc.)
  properties: JSON ({"value": "aspirin", "confidence": 0.95, "feedback_history": [...]})
  document_id: FK → documents.id INDEXED
  project_id: FK → projects.id INDEXED
  created_at, updated_at: DateTime
  
  # Discovery OS feedback nodes store experimental results:
  # {hit_id, smiles, result_name, result_value, unit, passed, notes, feedback_history: []}

edges (Knowledge Graph Relationships)
  id: String PK (UUID)
  source_id: FK → nodes.id INDEXED NOT NULL
  target_id: FK → nodes.id INDEXED NOT NULL
  type: String INDEXED ("CAUSES", "INHIBITS", "TREATS", "CO_OCCURS", etc.)
  properties: JSON (evidence quotes, confidence)
  document_id: FK → documents.id INDEXED
  project_id: FK → projects.id INDEXED
  created_at: DateTime
  INDEX(source_id, target_id)
```

---

## 4. Backend API (All Endpoints)

### Health & Config
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check with service architecture info |
| GET | `/health` | Lightweight health (Tauri polls this) |
| GET | `/config/keys` | API key availability flags |
| POST | `/config/keys` | Update API keys (persists to .env) |
| POST | `/config/keys/verify` | Verify each API key with minimal call |

### Models
| Method | Path | Description |
|--------|------|-------------|
| GET | `/models` | List available .gguf + embedding + NER models |
| GET | `/models/status` | Current LLM status (model, device, GPU layers) |
| POST | `/models/load` | Load local GGUF or cloud API model |
| GET | `/models/registry` | Full registry: local + cloud with key status |

### Projects
| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects` | Create project |
| GET | `/projects` | List all projects |
| DELETE | `/projects/{id}` | Delete project + cascade all data |

### Documents
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest` | Upload PDF/DOCX/TXT → background processing |
| GET | `/files` | List documents (filter: status, project_id) |
| GET | `/files/{id}` | Stream PDF file for viewing |
| DELETE | `/files/{id}` | Delete document from all layers |

### Chat (Librarian RAG)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Query knowledge layer → `{answer, reasoning, citations, relationships}` |

### Knowledge Graph
| Method | Path | Description |
|--------|------|-------------|
| GET | `/entities` | List nodes (filter: type, doc, project) |
| GET | `/entities/{id}/relationships` | Node relationships (direction: both/in/out) |
| GET | `/graph/types` | Node labels with counts |
| GET | `/graph/full` | Complete graph (nodes + edges), cached |

### Two-Brain Swarm (SSE Streaming)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/swarm/stream` | Stream Navigator/Cortex execution via SSE |
| POST | `/api/swarm/run` | Non-streaming swarm execution |

**SSE event types**: `routing`, `progress`, `thinking`, `chunk`, `evidence`, `grounding`, `graph_analysis`, `complete`, `cancelled`, `error`

### Mixture of Experts (SSE Streaming)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/moe/stream` | Stream MoE pipeline (hypothesis→retrieval→writer→critic) |
| POST | `/api/moe/run` | Non-streaming MoE |
| POST | `/api/moe/hypotheses` | Stream interactive hypothesis generation (user-in-the-loop) |

**SSE event types**: `routing`, `progress`, `hypotheses`, `evidence`, `grounding`, `complete`

### Intent Routing
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/route` | Classify intent WITHOUT execution → `{intent: SIMPLE|DEEP_DISCOVERY|BROAD_RESEARCH|MULTI_STEP|DISCOVERY}` |

### Discovery OS (Chemistry, SSE Streaming)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/discovery/stream` | Stream ReAct tool-calling loop |
| POST | `/api/discovery/run` | Non-streaming Discovery |
| POST | `/api/discovery/upload-spectrum` | Upload .jdx NMR spectrum file |
| POST | `/api/discovery/feedback` | Submit bioassay results → knowledge graph (Stage 7) |

**Request**: `{ hit_id, epoch_id, result_name, result_value, unit, passed, notes }`

**Response**: `{ status: "ok", updated_node_ids: [...] }`

**SSE event types**: `routing`, `progress`, `thinking`, `tool_call`, `tool_result`, `evidence`, `complete`

### Context Engine
| Method | Path | Description |
|--------|------|-------------|
| GET | `/files/{id}/structure` | Paper structure (title, methods, findings) |
| GET | `/files/{id}/related` | Related passages across docs |
| GET | `/files/{id}/chunks` | Document chunks (page filtering) |
| POST | `/api/context` | Context-aware suggestions |

### Import/Export
| Method | Path | Description |
|--------|------|-------------|
| POST | `/import/bibtex` | Import .bib or .ris files |
| GET | `/export/bibtex/{project_id}` | Export citations as .bib |
| POST | `/export/markdown` | Export as Pandoc Markdown |
| POST | `/export/chat` | Export chat as Markdown |
| POST | `/export/citations/format` | Format in APA/MLA/Chicago |

### Streaming Mechanics
- **Protocol**: Server-Sent Events (SSE) over POST
- **Cancellation**: Frontend AbortController → backend `asyncio.Event` via `monitor_disconnect()` polling
- **Headers**: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`
- **Timeout**: 300s (swarm), 180s (chat), 30s (simple)

---

## 5. LLM Service

**File**: `src/backend/app/services/llm.py` — Singleton `LLMService`

### Model Loading
- **Local**: llama-cpp-python loads `.gguf` from `src/backend/models/`
- **Priority**: Phi-3.5-mini → Qwen2.5-3B → Llama-3-8B → first .gguf
- **GPU**: Auto-detects CUDA, offloads 35 layers (RTX 3050 4GB VRAM)
- **Windows CUDA**: `_add_cuda_dll_directories()` registers nvidia DLL paths
- **Cloud**: LiteLLM routes to DeepSeek/MiniMax/OpenAI/Anthropic APIs

### Chat Templates
- `_model_type` auto-detected from filename: `"llama"` | `"qwen"` | `"phi3"` | `"api"`
- `_format_llama3_prompt()` — `<|start_header_id|>` tokens
- `_format_qwen_prompt()` — `<|im_start|>` ChatML tokens
- `_format_phi3_prompt()` — `<|system|>...<|end|>` tokens

### Key Methods
```python
async def generate(prompt, temperature=0.1, max_tokens=2048, stop=None) -> str
async def generate_constrained(prompt, schema, temperature=0.1, max_tokens=2048) -> dict
    # Local: GBNF grammar from JSON schema
    # API: response_format={"type": "json_object"}
async def generate_chat(system_message, user_message, ...) -> str
async def embed(text) -> List[float]  # 768-dim nomic-embed-text-v1.5
async def embed_batch(texts) -> List[List[float]]
async def load_model(model_name) -> str  # Switches model, frees VRAM
async def load_api_model(model_name) -> str  # Switches to cloud API
```

### Embedding
- **Model**: `nomic-embed-text-v1.5` (768 dimensions)
- **Storage**: Qdrant embedded mode (`./qdrant_storage`)
- **Thread-safe**: `_embed_lock` prevents concurrent inference

---

## 6. Agentic Pipelines

### 6.1 Two-Brain Swarm (`swarm.py`)

LangGraph `StateGraph` with `TypedDict(total=False)` state (NO Pydantic).

**Router** classifies query → routes to Navigator or Cortex.

**Navigator (Deep Discovery)**:
```
plan → retrieve → analyze → hypothesize → reflect
  ↑                                          │
  └────── REFINE/RETRIEVE_MORE ──────────────┘
```
- Reflection loop: up to 3 iterations
- Confidence threshold: 0.75 auto-pass
- Constrained JSON output via GBNF grammar (PLANNER_SCHEMA, CRITIC_SCHEMA)

**Cortex (Broad Research)**:
```
decompose → [execute_subtask × N] → cross_check → resolve_conflicts → synthesize
```
- Serial subtask execution (4GB VRAM constraint)
- Cross-checking detects contradictions between subtask results
- Conflict resolution with severity ratings

**Constrained Generation Schemas**:
- `PLANNER_SCHEMA`: understanding, information_needs, search_terms, potential_gaps
- `CRITIC_SCHEMA`: verdict (PASS|REFINE|RETRIEVE_MORE), issues_found, contradictions
- `DECOMPOSER_SCHEMA`: aspects, sub_tasks, coverage_check
- `CROSS_CHECKER_SCHEMA`: contradictions, coverage_gaps, overall_verdict
- `RESOLVER_SCHEMA`: resolutions with conflict_id and confidence

### 6.2 Mixture of Experts (`moe.py`)

Pipeline: `supervisor → hypothesis_agent → retrieval_agent → writer_agent → critic_agent`

- **Supervisor**: Selects experts, manages rounds (up to 5)
- **Hypothesis Agent**: Generates 3 distinct hypotheses
- **Retrieval Agent**: Deep RAG per hypothesis
- **Writer Agent**: Synthesizes evidence into answer
- **Critic Agent**: Fact-checks, requests revisions
- **User-in-the-loop**: Frontend shows hypothesis cards for selection

### 6.3 Discovery OS ReAct Agent (`agents/discovery_graph.py`)

```
think → decide(tool_call) → execute(plugin) → observe → think → ... → final_answer
```

- **Max iterations**: 8
- **Tool calling**: Constrained JSON with `TOOL_CALL_SCHEMA`
- **Input validation**: `validate_tool_input()` with aliases and repairs
- **Phase-aware tools**: Different tool sets per workflow phase

**Plugins** (BasePlugin ABC → PluginManager singleton):
| Plugin | What it does | Input |
|--------|-------------|-------|
| `predict_properties` | RDKit MW, LogP, HBD, HBA, TPSA, QED | `{smiles}` |
| `check_toxicity` | SMARTS/PAINS alert screening | `{smiles}` |
| `search_literature` | Bridges to existing RAG retrieval | `{query}` |
| `verify_spectrum` | NMR .jdx analysis via nmrglue | `{file_path, smiles}` |
| `plan_synthesis` | AiZynthFinder retrosynthesis | `{smiles}` |

### 6.4 Meta-Router (`meta_router.py`)

Intent classification: `SIMPLE` | `DEEP_DISCOVERY` | `BROAD_RESEARCH` | `MULTI_STEP` | `DISCOVERY`

- **Keyword fast-path**: Chemistry terms → DISCOVERY (avoids LLM call)
- **LLM fallback**: Constrained generation for ambiguous queries

### 6.5 Graph Service (`services/graph.py`)

SQLite-backed knowledge graph with NetworkX/Rustworkx integration.

**Query Methods**:
- `list_nodes(label?, document_id?, project_id?, limit=100)` — filtered node listing
- `get_node_relationships(node_id, direction='both')` — incoming/outgoing edges
- `get_node_types(project_id?)` — label distribution with counts
- `get_full_graph(document_id?, project_id?, limit=500)` — complete graph for visualization

**High-Performance Operations**:
- `get_rustworkx_subgraph()` — builds `PyDiGraph` (50x faster than NetworkX)
- Async cached wrappers (`@alru_cache`) for UI graph loading
- `invalidate_cache()` — clears caches after ingestion/feedback updates

**Discovery OS Feedback Integration (D5)**:
- `create_or_update_feedback_node(hit_id, epoch_id, result_name, result_value, unit, passed, notes, smiles?, project_id?)`
- Finds existing node by `hit_id` or `smiles`, updates with `feedback_history[]`
- Creates new node if not found, stores experimental results as node properties
- Returns list of updated/created node IDs

---

## 7. Retrieval Pipeline (`retrieval.py`)

Hybrid RAG with 7-stage fusion:

```
Query → [1] Vector Search (Qdrant, top-20)
      → [2] BM25 Sparse Search (top-20)
      → [3] Reciprocal Rank Fusion (k=60)
      → [4] Entity Matching (GLiNER extracted → graph lookup)
      → [5] Exact Text Matching (dates, key phrases)
      → [6] Graph Expansion (1-hop neighbors)
      → [7] FlashRank Reranking (top-5)
      → Answer Generation (LLM with formatted context)
```

- **Entity extraction from query**: LLM extracts entities, dates, key phrases
- **Document filtering**: Only chunks from `status="completed"` documents
- **Project scoping**: Optional `project_id` filter

---

## 8. Ingestion Pipeline (`ingest.py`)

```
Upload → SHA256 dedup check → Create Document record
       → Extract text (Docling VLM or pdfplumber fallback)
       → Chunk (semantic or fixed 1000/200)
       → Embed (nomic-embed-text-v1.5)
       → Store in Qdrant + SQLite chunks + BM25 index
       → GLiNER entity extraction → Node/Edge creation
       → Optional RAPTOR hierarchy
       → Mark completed
```

**Supported formats**: PDF, DOCX, DOC, TXT
**GLiNER labels**: chemical, protein, disease, gene, concept, person, organization, etc.
**Edge types** (ontology-enforced): CAUSES, INHIBITS, ENABLES, PART_OF, RELATED_TO, CONTRADICTS, SUPPORTS, TREATS, etc.

---

## 9. Frontend — Visual Design & User Experience

### 9.0 What the User Sees (Screen-by-Screen)

#### Screen 1: Projects Dashboard (`/`)
```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                         ATLAS                                │
│              Agentic RAG Knowledge Engine                    │
│                                                              │
│   ┌──────────────┐                                           │
│   │ Search...    │                                           │
│   └──────────────┘                                           │
│                                                              │
│   ┌─────────────────┐  ┌─────────────────┐                   │
│   │ ● Cancer Study  │  │ ● Drug Design   │                   │
│   │   3 documents   │  │   7 documents   │                   │
│   │   Created 2d    │  │   Created 1w    │                   │
│   └─────────────────┘  └─────────────────┘                   │
│                                                              │
│   [+ Create New Project]                                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```
- Near-black background (#070A0E), off-white text
- Project cards with green dot indicator, hover border glow
- Clean, minimal — no gradients, no clutter

#### Screen 2: Research Workspace (`/project/[id]`)

This is where 95% of the app lives. Three resizable panels:

```
┌─────────────────────────────────────────────────────────────────────┐
│ ← │ ● Cancer Research   Research Workspace │ Model ▾ │ GPU │ ⚙ │ ↓│
├────────┬─ [Docs] [Editor] [Graph] [Chat] [Canvas] ─┬───────────────┤
│        │                                            │               │
│  LIB   │          MAIN STAGE                        │   CONTEXT     │
│  RAR   │                                            │   ENGINE      │
│  Y     │  (changes based on active tab)             │               │
│        │                                            │  Smart        │
│  doc1  │                                            │  reading      │
│  doc2  │                                            │  suggestions  │
│  doc3  │                                            │  based on     │
│        │                                            │  selection    │
│  ───── │                                            │               │
│ Delete │                                            │          ◂▸   │
│ Project│                                            │               │
├────────┴────────────────────────────────────────────┴───────────────┤
│ (OmniBar overlay appears on Ctrl+K)                                │
└─────────────────────────────────────────────────────────────────────┘
```

**Header bar** (48px): Back arrow, project name with serif font + "Research Workspace" subtitle, node count, GPU indicator, model dropdown (local GGUF + cloud API), settings gear, export dropdown.

**Left panel — Library Sidebar** (18% width):
- File list with upload status badges (processing/completed/failed)
- Drag-and-drop upload zone
- Delete project button at bottom

**Center panel — Main Stage** (52% width):
- Tab bar: Documents | Editor | Graph | Deep Chat | Canvas
- Each tab renders a different view (see below)

**Right panel — Context Engine** (22% width):
- Shows reading suggestions based on current document selection
- Collapsible (shrinks to 40px icon strip)

#### Documents View
```
┌──────────────────────────────────────────────┐
│  filename.pdf                                │
│  ┌────────────────────────────────────────┐  │
│  │                                        │  │
│  │         PDF rendered here              │  │
│  │         (react-pdf)                    │  │
│  │                                        │  │
│  │         Page 3 of 24                   │  │
│  │                                        │  │
│  └────────────────────────────────────────┘  │
│  [Ask about this page]  [Related passages]   │
└──────────────────────────────────────────────┘
```
- Full PDF viewer with page navigation
- "Ask about this page" button pre-fills chat with question
- Related passages shows cross-document connections
- Also supports .txt, .md, .csv, .json via TextViewer

#### Graph View
```
┌──────────────────────────────────────────────┐
│                                              │
│        ◉ Aspirin ──TREATS──▸ ◉ Pain         │
│       ╱                       ╲              │
│  ◉ NSAID                   ◉ COX-2          │
│       ╲                       ╱              │
│        ◉ Ibuprofen──INHIBITS─▸              │
│                                              │
│  Legend: ◉ Chemical  ◉ Protein  ◉ Disease   │
└──────────────────────────────────────────────┘
```
- Force-directed graph (@xyflow/react + d3-force)
- Nodes colored by entity type (teal=Chemical, pink=Concept, etc.)
- Click node to expand relationships, hover for properties
- Zoom/pan/drag supported

#### Deep Chat View (the core interaction)
```
┌── [Librarian] [Cortex] [MoE] [Discovery] ── [🗑] ──┬──────────┐
│                                                      │          │
│         ┌─────────────────────────┐                  │  AGENT   │
│         │    Document Librarian   │                  │  WORK-   │
│         │    ◉ BookOpen icon      │                  │  BENCH   │
│         │                         │                  │          │
│         │  Answers backed by your │                  │ (appears │
│         │  documents with full    │                  │  only in │
│         │  citations.             │                  │  MoE &   │
│         └─────────────────────────┘                  │  Discov- │
│                                                      │  ery     │
│  ┌──────────────┐  ┌──────────────┐                  │  modes)  │
│  │"What are the │  │"Compare the  │                  │          │
│  │ key findings │  │ methods in   │                  │          │
│  │ in this      │  │ paper A & B" │                  │          │
│  │ paper?"      │  │              │                  │          │
│  └──────────────┘  └──────────────┘                  │          │
│  ┌──────────────┐  ┌──────────────┐                  │          │
│  │"Summarize    │  │"Find all     │                  │          │
│  │ the          │  │ mentions     │                  │          │
│  │ conclusions" │  │ of..."       │                  │          │
│  └──────────────┘  └──────────────┘                  │          │
│                                                      │          │
│  Press Ctrl+K to ask from any view                   │          │
│                                                      │          │
├──────────────────────────────────────────────────────┤          │
│ ⚡ Cortex (will switch)  ▾                           │          │
│ ┌────────────────────────────────────────────┐       │          │
│ │ What connections exist between aspirin     │ [→]   │          │
│ │ and cardiovascular outcomes?               │       │          │
│ └────────────────────────────────────────────┘       │          │
│  Shift+Enter new line              Ctrl+K anywhere   │          │
└──────────────────────────────────────────────────────┴──────────┘
```

**Mode tabs** (top): 4 pill-shaped buttons with mode-specific colors:
- Librarian (white/primary) — document Q&A
- Cortex (orange/accent) — deep research
- MoE (blue) — expert team
- Discovery (orange) — chemistry tools

**Empty state**: Mode icon in gradient bubble, title, description, 4 clickable example query cards, Ctrl+K hint.

**With messages**: Chat bubbles — user messages right-aligned (primary gradient), assistant left-aligned (card bg with border). Assistant messages include:
- Markdown rendering (headers, lists, code blocks, tables)
- Generative UI: MetricCards (colored stat boxes), ComparisonTables
- Brain activity trace (expandable): numbered reasoning steps
- Confidence score + iteration count badges
- Citation cards: source, page, relevance bar, grounding status
- **Follow-up taxonomy pills** (last message only):
  - `↓ Depth` (muted blue) — drill deeper into topic
  - `↔ Breadth` (muted teal) — explore related concepts  
  - `✗ Opposition` (muted amber) — challenge assumptions
- "View run details" link (opens RunAuditPanel)
- Error messages: red card with "Run again" retry button

**Routing badge** (above input): When typing >8 chars, a colored pill appears showing auto-detected mode (e.g., "⚡ Cortex") with dropdown to override.

**Input area**: Rounded textarea with send button (accent orange when text present). Discovery mode adds a paperclip button for .jdx spectrum uploads. Stop button appears during streaming.

**Side panels** (right, 450-500px):
- MoE mode: AgentWorkbench showing expert progress
- Discovery mode: DiscoveryWorkbench showing SMILES structures, property tables, toxicity results

**During streaming**: RunProgressDisplay shows:
- Routing indicator (which brain was selected)
- Elapsed time counter
- Pulsing dot with current action text
- Terminal-style thinking log (monospace, green cursor)
- Graph analysis card (if subgraph explored)
- Evidence counter
- Streaming text with typing cursor

#### OmniBar (Ctrl+K from any view)
```
┌──────────────────────────────────────────────┐
│ ⚡ What are the effects of aspirin on...     │
├──────────────────────────────────────────────┤
│  ⚡ Ask Atlas                   auto-detected│
│                                              │
│  ┌ ◉ Run with Librarian                   ┐ │
│  │   Document Q&A with citations           │ │
│  └─────────────────────────────────────────┘ │
│  ┌ ◉ Run with Cortex       [recommended]  ┐ │
│  │   Deep multi-agent research        ▓▓▓▓ │ │
│  └─────────────────────────────────────────┘ │
│  ┌ ◉ Run with MoE                         ┐ │
│  │   Expert team synthesis                 │ │
│  └─────────────────────────────────────────┘ │
│  ┌ ◉ Run with Discovery                   ┐ │
│  │   Chemistry tools & analysis            │ │
│  └─────────────────────────────────────────┘ │
├──────────────────────────────────────────────┤
│ ↑↓ navigate  ↵ select  esc close    ⚡ Enter│
│                                   to ask w/ │
│                                   Cortex    │
└──────────────────────────────────────────────┘
```
- Floating centered modal with backdrop blur
- When input looks like a question (>6 chars, question words, or 3+ words): shows "Ask Atlas" group with 4 mode options
- Auto-detected mode gets "recommended" badge and highlighted border
- When input looks like a command: shows Views, Actions, Navigation groups
- Footer shows keyboard shortcuts + "Enter to ask with [Mode]" hint

#### Run Audit Panel (slide-over from right)
```
                              ┌──────────────────────┐
                              │ Run History    [×]   │
                              │ 12 runs              │
                              ├──────────────────────┤
                              │ All Lib Ctx MoE Disc │
                              ├──────────────────────┤
                              │ ┌──────────────────┐ │
                              │ │ ◉ Cortex         │ │
                              │ │ "What connecti..." │
                              │ │ ✓ Completed 12.3s│ │
                              │ │ 8 events 3 src   │ │
                              │ └──────────────────┘ │
                              │ ┌──────────────────┐ │
                              │ │ ◉ MoE            │ │
                              │ │ "Synthesize..."   │ │
                              │ │ ✓ Completed 24.1s│ │
                              │ └──────────────────┘ │
                              │                      │
                              │ ── Event Timeline ── │
                              │ 0.0s routing→cortex  │
                              │ 0.2s progress:analyz │
                              │ 1.1s thinking:step 1 │
                              │ 3.4s evidence:5 found│
                              │ 8.2s grounding:92%   │
                              │ 12.3s complete        │
                              └──────────────────────┘
```
- Slide-in drawer (480px) with spring animation
- List view: filterable by mode, shows query preview, status badge, duration
- Detail view: full run metadata + expandable event timeline with JSON drill-down
- Accessible from OmniBar "Run History" command or "View run details" on messages

### 9.1 Design System

**Theme**: Dark void aesthetic
- Background: `#070A0E` (almost black)
- Card: `hsl(216 25% 6%)`
- Accent: `#FF4D2E` (safety orange)
- Text: `#F2F5F9` (off-white)

**Typography**:
- Display: Sora (headings)
- Body: Inter (13px base)
- Code: IBM Plex Mono

**UI libraries**: framer-motion, cmdk, lucide-react, @xyflow/react, d3-force, react-resizable-panels, react-pdf, react-markdown, class-variance-authority, tailwind-merge — NO shadcn/ui or Radix.

### 9.2 Workspace Layout (`workspace-page.tsx`)

```
┌──────────────────────────────────────────────────────┐
│ Header: Project name │ Model selector │ Export │ Settings │
├──────┬──────────────────────────────────┬────────────┤
│      │ [Docs] [Editor] [Graph] [Chat]  │            │
│  Lib │    [Canvas]                      │  Context   │
│  rar │                                  │  Engine    │
│  y   │   Main Stage                     │            │
│  Si  │   (active view renders here)     │  Smart     │
│  de  │                                  │  reading   │
│  bar │                                  │  suggest.  │
│      │                                  │            │
├──────┴──────────────────────────────────┴────────────┤
│ OmniBar (Ctrl+K) — floating command palette          │
│ RunAuditPanel — slide-over drawer (right)            │
└──────────────────────────────────────────────────────┘
```

5 views: Documents, Editor, Graph, Deep Chat, Canvas
3 resizable panels: Library (18%) | Main Stage (52%) | Context Engine (22%)

### 9.3 Chat System (Deep Chat View)

**ChatShell.tsx** — Container with 4 mode tabs:
- **Librarian** (green): Document Q&A with citations, non-streaming
- **Cortex** (orange/accent): Deep multi-agent streaming, reflection loops
- **MoE** (blue): Expert team, hypothesis selection UI
- **Discovery** (orange): Chemistry tools, ReAct streaming

**Data flow**:
```
User types → CommandSurface
  → debounced routeIntent() call → detectedMode badge
  → Enter/Submit → ChatShell.handleSubmit()
    → useRunManager.submitQuery() or submitLibrarian()
      → streamSSE() → NormalizedEvent stream
        → onProgress() updates StreamProgress
        → RunProgressDisplay shows live telemetry
      → result → addMessage() to chatStore
        → ConversationView renders with GenerativeRenderer
```

**Auto-routing**: As user types (>8 chars), ChatShell calls `POST /api/route` (debounced 500ms) to classify intent. CommandSurface shows a colored badge indicating detected mode with override option.

**OmniBar query submission**: From ANY view, `Ctrl+K` opens command palette. Typing a question shows "Ask Atlas" group with 4 mode options (recommended highlighted). Selecting one → switches to chat view → auto-submits.

### 9.3.1 Discovery OS Golden Path UI

The Discovery OS renders different Stage artifacts in the Main Stage based on `activeEpoch.currentStage`:

**Stage 1: PRIME — Mission Control Modal**
- Domain selector, target objective input
- Property constraint builder (MW, LogP, etc.)
- Corpus upload area
- "Initialize Discovery Session" button

**Stage 4: SURFACE — Candidate Artifact Grid**
```
┌─────────────────────────────────────────────────────────────┐
│ HIT #3  ·  Score: 0.87  ·  [Approve → Synthesis Plan]        │
│                          ·  [Reject]  ·  [Flag for Review]   │
├──────────────────────────┬──────────────────────────────────┤
│  [2D Molecule SVG]       │  Predicted Properties            │
│                          │  MW: 412.3 Da     ✓ < 500        │
│                          │  LogP: 3.1        ✓ 2–4          │
│                          │  hERG IC₅₀: 8.2μM  ⚠ borderline │
├──────────────────────────┴──────────────────────────────────┤
│ Source Reasoning:                                            │
│ "Scaffold derived from Chen_2023, Compound 7b..."            │
│ [View in Graph] [Find Similar] [Export Data]                 │
└─────────────────────────────────────────────────────────────┘
```
- Score badge color-coded (green >0.8, yellow 0.5-0.8, red <0.5)
- Approve triggers `forkEpoch()` to Stage 5
- Reject marks hit as rejected (reduced opacity overlay)

**Stage 6: SPECTROSCOPY — Validation View**
```
┌─────────────────────────────────────────────────────────────┐
│ SPECTROSCOPY VALIDATION  ·  Hit #3  ·  Run: #b9c1           │
├─────────────────────────────────────────────────────────────┤
│  [SVG Spectrum Chart: predicted vs observed peaks]          │
├─────────────────────────────────────────────────────────────┤
│  Predicted Signal        │  Observed Signal                 │
│  ─────────────────       │  ──────────────────────────      │
│  δ 7.42                 │  δ 7.41        ✓ match           │
│  δ 6.85                 │  NOT FOUND     ✗ missing         │
├─────────────────────────────────────────────────────────────┤
│  VERDICT:  ⚠  PARTIAL MATCH                                 │
│  3/4 predicted signals confirmed. Missing signal D.         │
├─────────────────────────────────────────────────────────────┤
│  [Proceed to Stage 7]  [Flag for re-evaluation]  [Export]   │
└─────────────────────────────────────────────────────────────┘
```
- SVG line chart with overlaid predicted (dashed) vs observed (solid) peaks
- Peak table with match/missing indicators
- Color-coded verdict box

**Stage 7: FEEDBACK — Bioassay Form**
```
┌─────────────────────────────────────────────────────────────┐
│ Experimental Feedback — Stage 7                             │
├─────────────────────────────────────────────────────────────┤
│ Approved Candidate: Hit #3 (Score: 0.92)                    │
├─────────────────────────────────────────────────────────────┤
│ Result Name: [IC50                ]  Unit: [μM      ]       │
│ Result Value: [42.5               ]  Pass/Fail: [✓ Pass]    │
│ Notes: [Additional observations...                         │
│                                                        ]    │
├─────────────────────────────────────────────────────────────┤
│                    [Submit Feedback]                        │
└─────────────────────────────────────────────────────────────┘
```
- Generic form fields (not chemistry-specific): Name, Value, Unit, Pass/Fail toggle, Notes
- On submit: creates/updates knowledge graph node with `feedback_history[]`
- Success state shows "Run another generation cycle →" button (forks to Stage 2)

### 9.4 State Management

**chatStore** (Zustand + localStorage persist):
- 4 isolated message arrays: `librarianMessages[]`, `cortexMessages[]`, `moeMessages[]`, `discoveryMessages[]`
- Per-mode input, session ID
- `pendingQuestion` (pre-fill from other views)
- `pendingHypotheses` (MoE user-in-the-loop)
- Follow-up taxonomy pills attached to assistant messages

**runStore** (Zustand + IndexedDB):
- `Run` objects with full event streams, tool invocations, results/errors
- States: queued → routing → running → completed/failed/cancelled
- IndexedDB persistence, 500 runs per project max, auto-pruned

**graphStore** (Zustand):
- `nodes[]`, `links[]` for @xyflow/react rendering
- Node colors by type (Chemical=#14b8a6, Concept=#ec4899, etc.)
- Focus/selection/expansion state

**discoveryStore** (Zustand + localStorage persist):
- **Epoch tree model**: Non-linear research branching
- `epochs: Map<string, Epoch>` — all epochs indexed by ID
- `activeEpochId`, `rootEpochId` — current position in tree
- **Golden Path stages**: 1 (PRIME) → 2 (GENERATE) → 3 (SCREEN) → 4 (SURFACE) → 5 (SYNTHESIS) → 6 (SPECTROSCOPY) → 7 (FEEDBACK)
- **Actions**:
  - `initializeSession(params)` — create root Epoch at Stage 1
  - `forkEpoch(parentId, reason, paramOverrides?, startStage?)` — branch to new Epoch
  - `switchToEpoch(epochId)` — switch active view
  - `approveHit(hitId)`, `rejectHit(hitId)` — Stage 4 candidate actions
  - `submitExperimentalResult(hitId, result)` — Stage 7 feedback
  - `advanceToStage(stage)` — progress Golden Path
- **Artifacts per Epoch**: `candidates[]`, `capabilityGaps[]`, `validations[]`, `feedbackResults[]`

### 9.5 Key Types

```typescript
// Chat message (stored in chatStore)
interface ChatMessage {
  id: string; role: 'user' | 'assistant'; content: string
  citations?: Citation[]
  brainActivity?: { brain: string; trace: string[]; evidence: any[]; confidenceScore?: number; iterations?: number; contradictions?: any[]; candidates?: any[] }
  librarianMetadata?: { reasoning?: string; relationships?: any[]; contextSources?: any }
  runId?: string
  errorInfo?: { category: string; message: string; retryable: boolean }
  followUps?: FollowUpSuggestions  // Depth/Breadth/Opposition pills (D4)
  timestamp: number
}

// Follow-up taxonomy (D4)
interface FollowUpSuggestion { label: string; query: string }
interface FollowUpSuggestions {
  depth: FollowUpSuggestion      // ↓ Drill deeper
  breadth: FollowUpSuggestion    // ↔ Explore related
  opposition: FollowUpSuggestion // ✗ Challenge assumptions
}

// Discovery OS Golden Path (discovery-types.ts)
type GoldenPathStage = 1 | 2 | 3 | 4 | 5 | 6 | 7

interface Epoch {
  id: string
  parentEpochId: string | null
  forkReason: string
  targetParams: ProjectTargetParams
  currentStage: GoldenPathStage
  createdAt: number
  candidates: CandidateArtifact[]
  capabilityGaps: CapabilityGap[]
  validations: SpectroscopyValidation[]
  feedbackResults: BioassayResult[]
  stageRuns: Partial<Record<GoldenPathStage, string>>
}

interface CandidateArtifact {
  id: string; rank: number; score: number
  renderType: 'molecule_2d' | 'crystal_3d' | 'polymer_chain' | 'data_table'
  renderData: any  // e.g., SMILES string
  properties: PredictedProperty[]
  sourceReasoning: string
  sourceDocumentIds: string[]
  status: 'pending' | 'approved' | 'rejected' | 'flagged'
  synthesisPlanRunId?: string
}

interface PredictedProperty {
  name: string
  value: number | string | boolean
  unit?: string
  passesConstraint: boolean | null
  model: string
}

interface SpectroscopyValidation {
  id: string; hitId: string; runId: string
  verdict: 'full_match' | 'partial_match' | 'no_match' | 'no_prediction_available'
  verdictText: string
  observedPeaks: SpectroscopyPeak[]
  predictedPeaks: SpectroscopyPeak[]
  matches: PeakMatch[]
  missing: SpectroscopyPeak[]
}

interface BioassayResult {
  id: string; hitId: string; epochId: string
  resultName: string; resultValue: number; unit: string
  passed: boolean; notes: string; submittedAt: number
}

// Normalized SSE event (stream-adapter.ts)
type NormalizedEvent =
  | { type: 'routing'; mode: string; intent: string }
  | { type: 'progress'; node: string; message: string }
  | { type: 'thinking'; content: string }
  | { type: 'tool_call'; tool: string; input: Record<string, any> }
  | { type: 'tool_result'; tool: string; output: Record<string, any> }
  | { type: 'evidence'; count: number }
  | { type: 'grounding'; claim: string; status: string; confidence: number }
  | { type: 'hypotheses'; items: any[] }
  | { type: 'graph_analysis'; data: any }
  | { type: 'chunk'; content: string }
  | { type: 'complete'; result: any }
  | { type: 'error'; message: string; category: FailureCategory }
  | { type: 'cancelled' }

// Run audit record (runStore.ts)
interface Run {
  id: string; mode: ChatMode; intent: string; query: string; projectId: string
  status: 'queued'|'routing'|'awaiting_override'|'running'|'awaiting_input'|'completed'|'failed'|'cancelled'
  startedAt: number; completedAt: number | null
  events: NormalizedEvent[]; toolInvocations: ToolInvocation[]
  result: any | null; error: { message: string; category: FailureCategory } | null
}

type ChatMode = 'librarian' | 'cortex' | 'moe' | 'discovery'
type FailureCategory = 'connectivity' | 'timeout' | 'stream_parse' | 'backend_validation' | 'backend_runtime' | 'user_cancelled'
```

### 9.6 Component Reference

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `ChatShell` | Chat container + orchestration | projectId, chatMode, onChatModeChange, autoSubmitQuery |
| `ConversationView` | Message rendering + generative UI + follow-up pills | messages, onCitationClick, onQuickQuery, onViewRunDetails, onFollowUpClick |
| `CommandSurface` | Input area + routing badge | value, onChange, onSubmit, detectedMode, onModeOverride |
| `RunProgressDisplay` | Streaming telemetry | streamProgress, streamingText, isLoading |
| `RunErrorDisplay` | Error cards + retry | category, message, onRetry |
| `RunAuditPanel` | Slide-over history + timeline | open, onClose, projectId, selectedRunId |
| `OmniBar` | Ctrl+K command palette + query | projectId, onSubmitQuery, onOpenRunHistory |
| `AgentWorkbench` | Swarm/MoE side panel | streamProgress, streamingText, isLoading |
| `DiscoveryWorkbench` | Chemistry ReAct terminal | streamProgress, isLoading, finalCandidates |
| **Discovery OS Components** |
| `CandidateArtifact` | Stage 4 candidate card | hit: CandidateArtifact |
| `SpectroscopyArtifact` | Stage 6 NMR/XRD validation | validation: SpectroscopyValidation |
| `BioassayFeedbackForm` | Stage 7 feedback submission | hit: CandidateArtifact, epochId: string |
| `KnowledgeGraph` | Entity/relationship vis | height, width, projectId, documentId |
| `PDFViewer` | PDF display + related passages | fileUrl, filename, docId, projectId |
| `EditorPane` | TipTap WYSIWYG editor | projectId |
| `ContextEngine` | Smart reading suggestions | projectId, selectedDocId, suggestions |
| `LibrarySidebar` | Document upload + list | onFileSelect, projectId |

---

## 10. Configuration Reference

### Settings (`config.py`) — Key Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `CHUNK_SIZE` | 1000 | Text chunk size (tokens) |
| `CHUNK_OVERLAP` | 200 | Overlap between chunks |
| `TOP_K_RETRIEVAL` | 5 | Top-K results for retrieval |
| `MAX_REFLECTION_ITERATIONS` | 3 | Navigator reflection limit |
| `NAVIGATOR_CONFIDENCE_THRESHOLD` | 0.75 | Auto-pass threshold |
| `CORTEX_NUM_SUBTASKS` | 5 | Cortex decomposition count |
| `ENABLE_RERANKING` | True | FlashRank reranking |
| `LLM_CONTEXT_SIZE` | 8192 | Context window |
| `LLM_N_BATCH` | 512 | Batch size |
| `MOE_HYPOTHESIS_COUNT` | 3 | Number of hypotheses |
| `MAX_TOOL_ITERATIONS` | 8 | ReAct loop limit |
| `GRAPH_CACHE_TTL` | 300 | Graph cache (seconds) |

### API Keys (stored in `config/.env`)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`
- Cloud models configured via `CLOUD_MODELS` comma-separated string

---

## 11. Development Commands

```powershell
# Full app (Tauri + Next.js)
npm run tauri:dev

# Backend only (hot-reload)
cd src/backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend only
cd src/frontend && npm run dev

# Build installer
npm run tauri:build

# Build backend bundle
npm run build:backend
```

---

## 12. Critical Patterns & Gotchas

1. **LangGraph state**: Uses `TypedDict(total=False)` — never Pydantic models inside state objects
2. **Streaming**: `compiled.astream_events(state, config, version="v2")` → yields on_chain_start/on_chain_end. Final state via `compiled.aget(config)`
3. **Memory**: `get_memory_saver()` returns shared `MemorySaver` singleton — session state lives for server process lifetime
4. **SSE cancellation**: Frontend AbortController → backend `asyncio.Event` via `monitor_disconnect()` polling
5. **Constrained generation**: Local = GBNF grammar (`LlamaGrammar.from_json_schema()`), API = `response_format={"type": "json_object"}`
6. **Chat templates**: Must match `_model_type` — wrong template = garbage output
7. **CUDA on Windows**: `_add_cuda_dll_directories()` must run before any llama-cpp-python import
8. **Schema changes**: SQLAlchemy doesn't auto-migrate — delete `atlas.db` and restart
9. **4GB VRAM constraint**: Subtasks execute serially in Cortex/MoE to avoid OOM
10. **Embedding model**: nomic-embed-text-v1.5 produces 768-dim vectors — Qdrant collection must match
11. **Frontend persist version**: chatStore uses version-keyed localStorage — bump version on schema change
12. **OmniBar auto-routing**: Calls `POST /api/route` debounced at 500ms to classify intent without execution
13. **Discovery OS Epoch forking**: `forkEpoch()` creates a snapshot copy of parent params; new Epoch starts at specified stage (default Stage 2). Original Epoch remains browsable.
14. **Follow-up taxonomy**: LLM appends `FOLLOW_UPS: {...}` JSON to response → backend parses and strips it → frontend renders as three pills only on last assistant message
15. **Stage 7 feedback loop**: Bioassay results create/update knowledge graph nodes with `feedback_history[]` array; enables iterative refinement via "Run another cycle" button
