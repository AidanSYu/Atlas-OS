# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🧠 Project Context & Agentic Protocol

**Project**: Atlas 2.0 (ContAInuum)
**Stack**: Tauri (Rust), FastAPI (Python), Next.js (TypeScript), Local LLMs, GraphRAG.
**Core Philosophy**: "The AI does not know things. It queries a living knowledge substrate."

### 🤖 The Agent Ecosystem (The Chain of Command)
You operate within a strict 3-tier hierarchy. You must identify your role in this chain.

**Level 1: Antigravity (The Planner)**
* **Role**: Project Manager & Orchestrator.
* **Responsibility**: Breaks complex user goals into step-by-step **Runbooks**.
* **Interaction**: You **receive** plans from Antigravity. If a task is vague, ask: *"Has Antigravity generated a plan for this yet?"*

**Level 2: Claude (The Architect - YOU)**
* **Role**: Lead Engineer & System Architect.
* **Responsibility**: Converts Antigravity's high-level steps into concrete code, file structures, and algorithms.
* **Interaction**: You **execute** the plan and **delegate** grunt work to Aider.

**Level 3: Aider (The Builder/QA)**
* **Role**: Junior Dev, QA, Debugger.
* **Stack**: `DeepSeek R1` (Planner) + `MiniMax 2.5` (Coder).
* **Responsibility**: TDD loops, fixing linting errors, writing tests, optimization.
* **Interaction**: You **command** Aider to verify your work.

---

### 🛠️ Workflow Protocols

**1. The Execution Loop (The "Antigravity Handoff")**
When the user pastes an Antigravity Runbook, your job is to execute **ONE step at a time**.
* **Read**: Analyze the current step in the Runbook.
* **Build**: Write the high-quality scaffolding/code (Python/React/Rust).
* **Delegate**: Immediately generate the **Aider Command** to verify that specific step.

**2. Aider Delegation Rules**
* **DO** use Aider to: Write unit tests, fix linting errors, debug stack traces, optimize performance, and hunt for security vulnerabilities.
* **DO NOT** use Aider to: Refactor the entire core architecture or rename 50 files at once (MiniMax will hallucinate the diffs).

**3. The Command Standard**
When asking Aider to work, use this format for reliability:
`aider <target_file> tests/<test_file> --message "Use R1 to plan: <Goal>. Then use MiniMax to: <Specific Task>."`

---

## 📁 Project Structure

```
Project Root
├── config/             # Configuration (.env, aider config, metadata)
├── installers/         # Compiled binaries (.exe/.msi)
├── scripts/            # Consolidated Scripts
│   ├── build/          # Build logic (build-backend.ps1)
│   ├── dev/            # Dev tools (launch_hybrid_aider, check_keys)
│   └── setup/          # Setup (setup_project.ps1)
├── src/                # Source Code
│   ├── backend/        # Python backend (FastAPI + SQLite + Qdrant)
│   ├── frontend/       # Next.js frontend (React + TypeScript)
│   └── tauri/          # Tauri wrapper (Rust)
└── tests/              # Test suites
```

---

## Development Commands

### Running the Application

```powershell
# Development mode (starts all components: Tauri window + Next.js frontend + FastAPI backend + SQLite + Qdrant)
npm run tauri:dev

# Frontend only (for UI development)
cd src/frontend
npm run dev

# Backend only (for API development)
cd src/backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Building the Application

```powershell
# Build production installer (.msi and .exe) - outputs to installers/
npm run tauri:build

# Build backend PyInstaller bundle only (with incremental build caching)
npm run build:backend

# Force rebuild backend (ignore cache)
powershell -ExecutionPolicy Bypass -File ./scripts/build/build-backend.ps1 -Force
```

### Dependency Management

```powershell
# Backend - if pip install hangs on langgraph/langchain-core backtracking
.\scripts\setup\setup-prereqs.ps1
```

## Architecture

### Multi-Layer Desktop Application

```
Atlas (Tauri Desktop Container)
├── Tauri Shell (Rust) [src/tauri/]
│   └── Manages sidecar processes (backend as bundled .exe)
├── Frontend (Next.js 14 + React + TypeScript) [src/frontend/]
│   ├── app/              # Pages and layouts
│   ├── components/       # UI components
│   │   ├── ChatInterface.tsx
│   │   ├── FileSidebar.tsx
│   │   ├── GraphCanvas.tsx
│   │   └── DualAgentChat.tsx (two-brain swarm UI)
│   └── lib/              # API client
└── Backend (FastAPI + SQLite + Qdrant) [src/backend/]
    ├── app/api/routes.py         # API endpoints
    ├── app/core/                 # Config, Database, Qdrant
    └── app/services/
        ├── ingest.py             # PDF → text → entities → vectors
        ├── retrieval.py          # Hybrid RAG (vector + text + graph)
        ├── graph.py              # Knowledge graph queries
        └── swarm.py              # Two-brain swarm (Navigator + Cortex)
```

### Database Schema (SQLite)
All models in `src/backend/app/core/database.py`.
Entities: **Project**, **Document**, **DocumentChunk**, **Node**, **Edge**.
Foreign Keys: Enabled (`PRAGMA foreign_keys=ON`).
Key Indexes: `idx_nodes_label`, `idx_edges_source_target`, `idx_documents_file_hash`.

### Two-Brain Swarm Architecture
`src/backend/app/services/swarm.py` implements LangGraph:
- **Router**: Classifies query (`DEEP_DISCOVERY` vs `BROAD_RESEARCH`).
- **Navigator**: Deep/sequential graph walking (NetworkX subgraph).
- **Cortex**: Map-reduce broad research (Serial execution for 4GB VRAM constraint).

### Vector Store & LLM
- **Qdrant**: Embedded mode (`./qdrant_storage`).
- **LLM Service**: llama-cpp-python with `_add_cuda_dll_directories()` for Windows GPU support.
- **Models**: `.gguf` LLaMA models, `nomic-embed-text-v1.5`, `gliner_small-v2.1`.
- **Location**: `src/backend/models/` (configured in `src/backend/app/core/config.py`).

## Key Files Reference

### Backend Critical Files
- `src/backend/app/main.py` - FastAPI app initialization + startup services
- `src/backend/app/api/routes.py` - `ensure_services()` initializes all services
- `src/backend/app/core/database.py` - SQLAlchemy models + SQLite setup
- `src/backend/app/services/retrieval.py` - Hybrid RAG (vector + entity + text search)
- `src/backend/app/services/swarm.py` - Two-brain swarm logic

### Frontend Critical Files
- `src/frontend/app/page.tsx` - Main application page
- `src/frontend/components/ChatInterface.tsx` - Primary chat UI
- `src/frontend/components/DualAgentChat.tsx` - Swarm interaction UI
- `src/frontend/lib/api.ts` - API client

### Build & Config
- `scripts/build/build-backend.ps1` - PyInstaller build script with incremental caching
- `scripts/setup/setup-prereqs.ps1` - Dependency installation script
- `src/tauri/tauri.conf.json` - Tauri configuration (sidecar, window, bundle)
- `src/backend/atlas.spec` - PyInstaller spec file
- `config/.env` - Environment variables

### Output
- `installers/` - Compiled `.exe` and `.msi` files

## Common Workflows

### Adding a New Service
1. **Antigravity Step**: "Define the new service scope."
2. **Claude Step**: Create service file in `src/backend/app/services/` and register in `routes.py`.
3. **Aider Step**: "Generate tests for the new service immediately."
   ```bash
   aider src/backend/app/services/new_feature.py tests/backend/test_new_feature.py --message "Create pytest unit tests for this service. Cover edge cases. Run tests until 100% pass."
   ```

### Working with Knowledge Graphs
- **Node creation**: `src/backend/app/services/ingest.py` (GLiNER).
- **Graph queries**: `src/backend/app/services/graph.py` (NetworkX).
- **Performance**: Use `joinedload()` to prevent N+1 queries.

### Adding a New API Endpoint
1. Add route handler to `src/backend/app/api/routes.py`
2. Add Pydantic models for request/response validation
3. Call service layer (e.g., `DocumentService`, `GraphService`)
4. Update frontend API client in `src/frontend/lib/api.ts`

### Modifying Database Schema
1. Update models in `src/backend/app/core/database.py`
2. Add indexes for foreign keys and frequently queried fields
3. In development: stop app, delete `atlas.db`, restart (auto-recreates)
4. **Important**: SQLAlchemy doesn't auto-migrate. Schema changes require DB recreation or manual ALTER statements.

## Testing & Quality Assurance

**Philosophy**: We use **Aider-First TDD**. We do not write manual tests. We instruct Aider to write them.

### The Testing Workflow
1. **Plan**: Antigravity defines the feature requirement.
2. **Create**: Claude scaffolds the feature (e.g., `src/backend/app/services/new_feature.py`).
3. **Delegate**: Claude generates the command:
   ```bash
   aider src/backend/app/services/new_feature.py tests/backend/test_new_feature.py --message "Create pytest unit tests for this service. Cover edge cases. Run tests until 100% pass."
   ```
4. **Verify**: User runs the Aider command.

### Manual Verification
- **UI**: Upload test PDFs, verify entity extraction in `nodes` table.
- **Swarm**: Test `DEEP_DISCOVERY` queries in the Chat Interface.
- **Database**: Inspect SQLite with `sqlite3 atlas.db`
- **Build**: Verify installer output in `installers/` directory.
