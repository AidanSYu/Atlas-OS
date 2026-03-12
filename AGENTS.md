# AGENTS.md - Atlas 2.0 (ContAInuum)

> This file provides comprehensive guidance to AI coding agents working on the Atlas project. Expect the reader to know nothing about the project.

## Project Overview

**Atlas 2.0** (Is a software by ContAInuum) is an AI-native knowledge management desktop application that builds a continuous knowledge layer beneath an AI model. It is a **standalone Windows desktop application** powered by a Multi-Agent LangGraph Architecture.

**Core Philosophy**: "The AI does not know things. It queries a living knowledge substrate."

### Key Features

- **Local-First Architecture** - All data stays on the user's computer. Zero cloud dependencies.
- **Agentic RAG (Swarm)** - Dynamic query routing via a Meta-Router to specialized agents (Librarian, Navigator, Cortex).
- **Multi-Turn Reflection Loops** - Agents plan, explore graphs, retrieve iteratively, and self-critique.
- **Knowledge Graph** - Entities and relationships stored in SQLite with Rustworkx for high-performance graph operations.
- **Constrained Generation** - Uses GBNF grammars with llama-cpp-python for reliable JSON output from small local models.
- **Hybrid RAG** - Combines vector search (Qdrant), knowledge graph traversal, and BM25 text retrieval.

---

## Technology Stack

### Three-Layer Architecture

```
Atlas (Desktop Application)
├── Frontend Layer (Next.js 14, React, TypeScript, Tailwind CSS)
│   └── Port: 3001 (dev) | Static export (production)
├── Tauri Shell (Rust)
│   └── Manages sidecar processes, window, native APIs
└── Backend Layer (Python/FastAPI)
    ├── FastAPI server (port 8000)
    ├── SQLite (embedded, no external server)
    ├── Qdrant vector store (embedded, path mode)
    ├── Rustworkx knowledge graph engine
    └── LangGraph multi-agent swarm
```

### Frontend Stack

| Component | Technology |
|-----------|------------|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript 5.3 |
| Styling | Tailwind CSS 3.4 |
| UI Components | Custom + Framer Motion |
| State Management | Zustand |
| Rich Text | Tiptap |
| Graph Visualization | @xyflow/react, react-force-graph-2d |
| Build Output | Static export to `out/` |

### Backend Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI 0.109 |
| Database | SQLite (SQLAlchemy 2.0) |
| Vector Store | Qdrant Client 1.12+ (embedded mode) |
| Graph Engine | Rustworkx 0.14+ |
| LLM Runtime | llama-cpp-python 0.2.83 |
| Embeddings | sentence-transformers (Nomic Embed Text) |
| NER | GLiNER (fast entity extraction) |
| Agent Framework | LangGraph 0.2+ |
| Document Parsing | Docling, pdfplumber, PyPDF |
| Reranking | FlashRank |
| Chunking | semantic-text-splitter (Rust-based) |

### Desktop Shell Stack

| Component | Technology |
|-----------|------------|
| Framework | Tauri 1.5 |
| Language | Rust (Edition 2021) |
| Build Tool | cargo tauri |
| Output | Windows MSI/EXE installer |

---

## Project Structure

```
Project Root
├── config/                  # Configuration files
│   ├── .env                 # Environment variables (gitignored)
│   ├── .env.example         # Template for env vars
│   ├── .aider.conf.yml      # Aider AI assistant config
│   └── .aiderignore         # Files to ignore in Aider
├── installers/              # Compiled binaries (.exe/.msi)
├── models/                  # AI models (gitignored)
│   ├── *.gguf              # LLM model files
│   ├── nomic-embed-text-v1.5/  # Embedding model
│   └── gliner_small-v2.1/  # NER model
├── scripts/                 # PowerShell automation scripts
│   ├── build/
│   │   └── build-backend.ps1    # PyInstaller build with caching
│   ├── dev/
│   │   ├── run_backend.ps1      # Start backend dev server
│   │   └── launch_hybrid_aider.ps1
│   └── setup/
│       └── setup_project.ps1    # Initial project setup
├── src/
│   ├── backend/            # Python FastAPI backend
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   └── routes.py        # API endpoints
│   │   │   ├── core/
│   │   │   │   ├── config.py        # Settings & env vars
│   │   │   │   ├── database.py      # SQLAlchemy models
│   │   │   │   ├── memory.py        # Working memory
│   │   │   │   └── qdrant_store.py  # Vector store
│   │   │   └── services/
│   │   │       ├── agents/          # LangGraph agents
│   │   │       │   ├── discovery_graph.py
│   │   │       │   ├── experts/     # MoE experts
│   │   │       │   ├── librarian.py
│   │   │       │   ├── meta_router.py
│   │   │       │   └── supervisor.py
│   │   │       ├── chat.py
│   │   │       ├── document.py
│   │   │       ├── graph.py
│   │   │       ├── ingest.py
│   │   │       ├── llm.py
│   │   │       ├── retrieval.py
│   │   │       └── swarm.py
│   │   ├── data/           # Runtime data (uploads, drafts)
│   │   ├── models/         # AI model storage
│   │   ├── requirements.txt
│   │   ├── requirements-dev.txt
│   │   └── run_server.py   # Entry point for PyInstaller
│   ├── frontend/           # Next.js frontend
│   │   ├── app/            # App router pages
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── project/
│   │   ├── components/     # React components
│   │   │   ├── chat/       # Chat-related components
│   │   │   ├── canvas/     # Graph canvas nodes
│   │   │   └── generative/ # Generative UI components
│   │   ├── lib/            # Utilities & API client
│   │   │   └── api.ts      # Backend API client
│   │   ├── public/         # Static assets
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── tauri/              # Rust desktop wrapper
│       ├── src/
│       │   └── main.rs     # Tauri main entry
│       ├── Cargo.toml
│       ├── tauri.conf.json
│       └── resources/      # Bundled backend (gitignored)
├── tests/                  # Test scripts and benchmarks
├── .venv/                  # Python virtual environment
├── package.json            # Root npm scripts
├── CLAUDE.md               # Claude Code specific guidance
└── README.md               # User-facing documentation
```

---

## Build and Development Commands

### Prerequisites

- **Windows 10/11** (x64)
- **Node.js 18+**
- **Python 3.12**
- **Rust** (for Tauri modifications)

### Initial Setup

```powershell
# Run setup script (installs dependencies)
.\scripts\setup\setup_project.ps1

# Or manual setup:
cd src/frontend
npm install
cd ../backend
python -m venv ../../.venv
.\..\..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Development Commands

```powershell
# Full Tauri development (recommended)
npm run tauri:dev

# Backend only (Terminal 1)
.\scripts\dev\run_backend.ps1
# Or manually:
cd src/backend
python run_server.py

# Frontend only (Terminal 2)
cd src/frontend
npm run dev
# Opens at http://localhost:3001
```

### Production Build

```powershell
# Build complete application (backend + frontend + Tauri installer)
npm run tauri:build

# Build only backend with caching
npm run build:backend

# Force rebuild backend (ignore cache)
powershell -ExecutionPolicy Bypass -File ./scripts/build/build-backend.ps1 -Force
```

**Output**: Installers are placed in `installers/` directory as `.msi` and `.exe` files.

---

## Code Style Guidelines

### Python Backend

- **Style**: PEP 8 compliant
- **Type Hints**: Use explicit type annotations for function signatures
- **Docstrings**: Google-style docstrings for modules and functions
- **Imports**: Group as (1) stdlib, (2) third-party, (3) local app imports
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Error Handling**: Use explicit exception handling with logging

Example:
```python
"""Module description."""
from typing import Optional
import logging

from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


def process_item(item_id: str) -> Optional[dict]:
    """Process a single item by ID.
    
    Args:
        item_id: Unique identifier for the item.
        
    Returns:
        Processed item data or None if not found.
        
    Raises:
        HTTPException: If processing fails.
    """
    try:
        # Implementation
        pass
    except Exception as e:
        logger.error(f"Failed to process {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Processing failed")
```

### TypeScript Frontend

- **Style**: ESLint + Prettier (configured in package.json)
- **Components**: Functional components with explicit return types
- **Props**: Interface definitions for all component props
- **State**: Use Zustand for global state, useState for local state
- **Naming**: `camelCase` for variables/functions, `PascalCase` for components/interfaces

Example:
```typescript
interface ChatMessageProps {
  message: Message;
  onDelete?: (id: string) => void;
}

export function ChatMessage({ message, onDelete }: ChatMessageProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);
  
  return (
    // Component JSX
  );
}
```

### Frontend Design Guidelines

When writing frontend code, reject "AI slop" aesthetics:

1. **Design Direction**: Commit to a visual direction (retro-futuristic, editorial, brutalist, luxury)
2. **Typography**: Use distinctive font pairings (display + body), avoid generic fonts
3. **Layout**: Use asymmetry, intentional overlapping, generous negative space
4. **Motion**: CSS-only animations for hover/load states, staggered reveals
5. **Color**: Use CSS variables for themes, add depth via textures/gradients

---

## Testing Strategy

### Testing Philosophy

This project uses **Aider-First TDD**:
1. Claude scaffolds the feature
2. Aider (DeepSeek R1 + MiniMax) writes and verifies tests

### Test Commands

```powershell
# Backend tests with pytest
cd src/backend
pytest

# Frontend linting
cd src/frontend
npm run lint

# Type checking
npx tsc --noEmit
```

### Manual Verification

- **UI**: Upload test PDFs, verify entity extraction in `nodes` table
- **Swarm**: Test `DEEP_DISCOVERY` queries in Chat Interface
- **Database**: Inspect SQLite with `sqlite3 atlas.db`
- **Build**: Verify installer output in `installers/` directory

---

## Database Schema

### SQLite Tables (SQLAlchemy Models in `src/backend/app/core/database.py`)

```
Project                    # Research project scope
├── id (PK)
├── name
├── description
└── created_at/updated_at

Document                   # Uploaded files
├── id (PK)
├── filename
├── file_hash (indexed)
├── project_id (FK)
└── upload_date

DocumentChunk              # Text chunks for retrieval
├── id (PK)
├── document_id (FK)
├── chunk_index
├── text_content
└── embedding

Node                       # Knowledge graph entities
├── id (PK)
├── label (indexed)        # e.g., "chemical", "concept"
├── properties (JSON)
├── document_id (FK)
└── project_id (FK)

Edge                       # Knowledge graph relationships
├── id (PK)
├── source_id (FK)
├── target_id (FK)
├── edge_type
└── properties (JSON)
```

**Indexes**: `idx_nodes_label`, `idx_edges_source_target`, `idx_documents_file_hash`

**Foreign Keys**: Enabled (`PRAGMA foreign_keys=ON`)

---

## Agent Architecture

### Multi-Agent Swarm (LangGraph)

```
User Query
    ↓
Meta-Router (Intent Classification)
    ├─> Simple Query → Librarian Agent (Fast Vector Search)
    ├─> Deep Discovery → Navigator 2.0 (Graph walk + reflection)
    └─> Broad Research → Cortex MoE (Mixture of Experts)
           ↳ Supervisor → Hypothesis/Retrieval/Writer Experts
           ↳ Grounding Auditor → Validates citations
```

### Key Agent Files

| Agent | File | Purpose |
|-------|------|---------|
| Meta-Router | `services/agents/meta_router.py` | Classifies query intent |
| Librarian | `services/agents/librarian.py` | Direct vector search |
| Navigator | `services/agents/discovery_graph.py` | Deep graph exploration |
| Supervisor | `services/agents/supervisor.py` | Coordinates MoE |
| Experts | `services/agents/experts/` | Specialized sub-agents |

---

## Configuration

### Environment Variables (`config/.env`)

```bash
# Required API Keys for Aider
DEEPSEEK_API_KEY=xxx
MINIMAX_API_KEY=xxx

# Optional: Cloud LLM APIs
OPENAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx

# Backend Configuration (dev overrides)
API_PORT=8000
DATABASE_URL=sqlite:///./atlas.db
```

### Application Settings (`src/backend/app/core/config.py`)

Key configuration options:
- `ENABLE_NAVIGATOR_REFLECTION`: Multi-turn reasoning for Navigator
- `MAX_REFLECTION_ITERATIONS`: Cap on reflection loops (default: 3)
- `ENABLE_RERANKING`: FlashRank reranking for RAG
- `USE_DOCLING`: VLM-based document parsing
- `LLM_CONTEXT_SIZE`: Token context window (default: 8192)

---

## Security Considerations

### Data Privacy

- **Local-First**: All data stored locally in user's AppData
- **No Cloud Dependencies**: Models run locally via llama.cpp
- **Optional API Keys**: Cloud LLMs only used if keys provided

### CSP (Content Security Policy)

Configured in `src/tauri/tauri.conf.json`:
```json
"csp": "default-src 'self'; connect-src 'self' http://127.0.0.1:8000 ..."
```

### CORS

Backend only accepts connections from:
- `tauri://localhost`
- `https://tauri.localhost`
- `http://localhost:3000`
- `http://localhost:3001`

---

## Common Development Workflows

### Adding a New API Endpoint

1. Add Pydantic models in `src/backend/app/api/routes.py`
2. Implement route handler with service layer call
3. Update frontend API client in `src/frontend/lib/api.ts`
4. Test with Aider: `aider tests/backend/test_new_endpoint.py`

### Modifying Database Schema

1. Update models in `src/backend/app/core/database.py`
2. Add indexes for frequently queried fields
3. **Important**: SQLAlchemy doesn't auto-migrate
4. Dev: Stop app, delete `atlas.db`, restart (auto-recreates)
5. Production: Manual migration scripts required

### Adding a New Agent

1. Create agent file in `src/backend/app/services/agents/`
2. Register in `routes.py` service initialization
3. Connect to Meta-Router for query routing
4. Generate tests via Aider

### Working with Knowledge Graphs

- **Node creation**: `src/backend/app/services/ingest.py` (GLiNER extraction)
- **Graph queries**: `src/backend/app/services/graph.py` (Rustworkx)
- **Performance**: Use `joinedload()` to prevent N+1 queries

---

## Troubleshooting

### Port Already in Use

```powershell
# Find process
netstat -ano | findstr :8000

# Kill process
taskkill /PID <PID> /F
```

### Backend Won't Start

1. Check Python venv is activated
2. Verify `MODELS_DIR` env var is set
3. Check logs in terminal for import errors
4. Ensure port 8000 is free

### Frontend Won't Connect

1. Verify backend is running on port 8000
2. Check CORS settings in `app/main.py`
3. Verify CSP in `tauri.conf.json` allows localhost:8000
4. Check browser console for errors

### Tauri Black Screen

1. Ensure frontend dev server started on port 3001
2. Check `beforeDevCommand` in `tauri.conf.json`
3. Verify `devPath` points to correct URL

---

## Key File Reference

### Backend Critical Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI initialization, startup/shutdown |
| `app/api/routes.py` | All API endpoints, service initialization |
| `app/core/config.py` | Settings, environment variables |
| `app/core/database.py` | SQLAlchemy models, SQLite setup |
| `app/services/llm.py` | LLM service with llama.cpp |
| `app/services/retrieval.py` | Hybrid RAG (vector + graph + text) |
| `app/services/swarm.py` | Two-brain swarm orchestration |
| `run_server.py` | PyInstaller entry point |

### Frontend Critical Files

| File | Purpose |
|------|---------|
| `app/page.tsx` | Main application page |
| `components/ChatInterface.tsx` | Primary chat UI |
| `components/DualAgentChat.tsx` | Swarm interaction display |
| `lib/api.ts` | Backend API client |

### Build & Config Critical Files

| File | Purpose |
|------|---------|
| `scripts/build/build-backend.ps1` | PyInstaller build with caching |
| `src/tauri/tauri.conf.json` | Tauri window, security, bundle config |
| `src/tauri/Cargo.toml` | Rust dependencies |
| `src/tauri/src/main.rs` | Tauri main entry, sidecar management |

---

## Agent Ecosystem (Development Workflow)

This project operates within a 3-tier AI agent hierarchy:

### Level 1: Antigravity (The Planner)
- **Role**: Project Manager & Orchestrator
- **Responsibility**: Breaks complex goals into step-by-step Runbooks
- **Interaction**: Receives plans, executes one step at a time

### Level 2: Claude (The Architect)
- **Role**: Lead Engineer & System Architect (YOU)
- **Responsibility**: Converts plans into concrete code and structures
- **Interaction**: Executes plans and delegates to Aider

### Level 3: Aider (The Builder/QA)
- **Role**: Junior Dev, QA, Debugger
- **Stack**: DeepSeek R1 (Planner) + MiniMax 2.5 (Coder)
- **Responsibility**: TDD loops, linting fixes, test writing
- **Command Format**: `aider <file> tests/<test_file> --message "Use R1 to plan: <Goal>. Then MiniMax to: <Task>."`

---

## License

MIT License - See `LICENSE` file for details.

---

**Last Updated**: February 2026  
**Version**: 2.0.0  
**Status**: Production Ready
