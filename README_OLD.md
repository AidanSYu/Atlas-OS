# Atlas 2.0 - AI-Native Knowledge Desktop Application

> **The AI does not know things. It queries a living knowledge substrate.**

Atlas 2.0 is a **standalone Windows desktop application** that builds a continuous knowledge layer beneath an AI model. This is not a chatbot—it's a scalable, explainable, open-source knowledge substrate optimized for retrieval, relationships, and reasoning over your personal documents.

**New in 2.0:** Fully self-contained desktop app (no external servers, no Docker required). All components bundled: PostgreSQL, Qdrant vector database, and Python backend run as secure local processes.

---

## ✨ Key Features

- **Local-First Architecture** - All data stays on your computer. Zero cloud dependencies.
- **One-Click Install** - Windows installer includes everything needed (no prerequisite installation)
- **Transparent Reasoning** - System explains *why* it gives each answer with full source citation
- **Relationship Queries** - Ask "How are X and Y connected?" and get graph-based answers
- **Document Grounding** - All answers cite source documents and page numbers
- **Knowledge Graph** - Entities and relationships queryable independently  
- **Fast NER** - GLiNER-based entity extraction (~50x faster than LLM-based extraction)
- **Async Processing** - Non-blocking document ingestion with background tasks
- **No External Dependencies** - Completely self-contained; no Ollama, no Docker, no cloud services

---

## 🚀 Installation & Usage

### For Users: Install the Application

1. **Download** the latest installer from [Releases](https://github.com/[your-repo]/releases)
   - `Atlas_2.0.0_x64_en-US.msi` (Windows Installer) - Recommended
   - `Atlas_2.0.0_x64-setup.exe` (Alternative installer)

2. **Run** the installer and follow the setup wizard

3. **Launch** Atlas from your Start Menu or Desktop shortcut

4. **Add Documents**:
   - Click "Upload Documents" or drag-and-drop PDF files
   - Atlas automatically extracts text, entities, and relationships
   - Query your knowledge base immediately

5. **Ask Questions**:
   - Type natural language questions
   - System returns answers with source citations and relationship context

---

## 🛠️ Development & Building

### Prerequisites (For Developers)

- **Windows 10/11** (x64)
- **Node.js 18+** - https://nodejs.org/
- **Python 3.12** - https://www.python.org/ (already bundled in releases)
- **Rust** (optional) - Required only to modify Tauri/desktop components

### Quick Start: Development Mode

```powershell
# Clone the repository
git clone https://github.com/[your-repo]/atlas.git
cd atlas

# Install dependencies
npm install

# Run development server (all components in one window)
npm run tauri:dev
```

This launches:
- ✅ Backend (FastAPI) on `http://localhost:8000`
- ✅ PostgreSQL (bundled executable)
- ✅ Qdrant (bundled executable)
- ✅ Frontend (Next.js) on `http://localhost:3000`
- ✅ Desktop window with embedded web view

**Note:** Only works on Windows; Linux/Mac support coming with Tauri 2.0

### Build Production Installer

```powershell
# Build backend PyInstaller executable + frontend bundle + Tauri app
npm run tauri:build
```

This creates:
- `src-tauri/target/release/Atlas_2.0.0_x64_en-US.msi` - Windows Installer
- `src-tauri/target/release/Atlas_2.0.0_x64-setup.exe` - Alternative installer
- ~2.8GB total size (includes all dependencies and models)

---

## 🏗️ Architecture

### Desktop Application Structure

```
Atlas (Windows Application)
├── Frontend Layer
│   ├── Next.js 14 (React) - UI
│   ├── TailwindCSS - Styling
│   └── TypeScript - Type safety
│
├── Tauri Shell (Desktop Bridge)
│   ├── Rust core
│   ├── Window management
│   ├── Sidecar process orchestration
│   └── File system access
│
└── Backend Layer (Bundled Sidecars)
    ├── FastAPI (Python) - API server
    ├── PostgreSQL 16.1 - Graph + Document Store
    ├── Qdrant v1.7.0 - Vector Database
    ├── PyInstaller bundle - All Python dependencies
    └── Models (LLaMA, embeddings, GLiNER)
```

### Knowledge Layer Architecture

```
User Query (Desktop UI)
    ↓
FastAPI Backend
    ↓
Retrieval Orchestrator (Hybrid RAG)
    ├─ Vector Search (Qdrant)
    ├─ Entity Matching (PostgreSQL)
    ├─ Text Search (PostgreSQL Full-Text)
    └─ Relationship Discovery
    ↓
Knowledge Graph (PostgreSQL)
    ├─ Entities (extracted via GLiNER)
    ├─ Relationships (semantic connections)
    ├─ Document References
    └─ Metadata
    ↓
LLM Response Synthesis (LLaMA)
    ↓
Source-Cited Answer + Explanations
```

---

## 📦 Component Details

### Backend Services (Python/FastAPI)

**`backend/app/services/`** - Core services:
- `ingest.py` - PDF ingestion → text extraction → entity/relationship extraction → storage
- `retrieval.py` - Hybrid RAG with vector + entity + text search
- `document.py` - Document CRUD with automatic cleanup
- `graph.py` - Knowledge graph queries with optimized relationship loading
- `chat.py` - Chat orchestration with response generation
- `llm.py` - Local LLM wrapper (LLaMA via llama-cpp-python)

**Database Setup** (`backend/app/core/database.py`):
- PostgreSQL for structured data (graph + documents)
- Qdrant for semantic vectors
- Both run as local Windows executables

### Frontend (React/Next.js)

**`frontend/`** - User interface:
- `/app` - Main pages and layouts
- `/components` - Reusable UI components (ChatInterface, FileSidebar, GraphCanvas, etc.)
- `/lib` - API client and utilities

### Desktop Container (Rust/Tauri)

**`src-tauri/src/main.rs`** - Tauri orchestration:
- Starts PostgreSQL + Qdrant sidecars on app launch
- Routes desktop window ↔ FastAPI backend
- Manages process lifecycle (cleanup on exit)

---

## ⚡ Performance Optimizations

### Query Performance
| Operation | Performance | Notes |
|-----------|-------------|-------|
| Entity relationships (100 nodes) | 3 queries | 98.5% reduction from N+1 optimization |
| Active document filtering (10K docs) | O(log n) | FK-based JOIN instead of IN clause |
| Graph expansion | ~50ms | Eager-loaded relationships |
| Full-text search | <100ms | PostgreSQL native FTS |

### Concurrency
- **Event loop** - Non-blocking async/await throughout
- **Max concurrent users** - 100+ on typical hardware
- **Qdrant search** - Run in executor to prevent blocking

### Build Time
- **Incremental builds** - PyInstaller caching (checks source file timestamps)
- **Skip Python rebuild** - If backend source unchanged, skip 10-minute compile
- **Model bundling** - Optional (`-IncludeModels` flag for offline use)

### Recent Fixes Applied
1. ✅ Eliminated N+1 queries in graph relationships
2. ✅ Replaced JSONB filtering with indexed FK lookups
3. ✅ Fixed blocking I/O in async functions (Qdrant searches)
4. ✅ Added request timeouts and proper error handling
5. ✅ Implemented cascading deletes for data integrity

---

## 🔧 Configuration

### Environment Variables

All configuration is automatic for the desktop app. For development, set in `backend/.env`:

```env
# Database
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=atlas_knowledge
POSTGRES_USER=atlas
POSTGRES_PASSWORD=atlas_secure_password

# Vector Store
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333

# Model Paths
MODELS_DIR=./models
```

**Notes:**
- All paths are local; no network dependencies
- Models auto-download on first run (~2-3GB)
- Data stored in `%APPDATA%\Atlas\data\`

---

## 📝 Development Workflow

### Making Changes

**Backend Service Changes:**
```powershell
# Edit backend/app/services/*.py
# Changes auto-reload via uvicorn --reload
# Just refresh the desktop window to see changes
```

**Frontend Changes:**
```powershell
# Edit frontend/app/*.tsx or frontend/components/*.tsx
# Changes auto-reload via Next.js HMR
# Desktop window updates automatically
```

**Database Schema Changes:**
```powershell
# Edit backend/app/core/database.py
# Stop (Ctrl+C) and restart: npm run tauri:dev
# Database is recreated on schema change (development only)
```

### Testing

```powershell
# Run tests
npm test                      # Frontend tests
python -m pytest backend/     # Backend tests

# Type checking
npm run type-check           # TypeScript check
```

### Debugging

**Backend Logs:**
- Terminal output from `npm run tauri:dev` shows FastAPI logs
- Check browser console (F12) for frontend errors

**Database Issues:**
- PostgreSQL log: `data/postgres/postgresql.log`
- Qdrant log: `src-tauri/resources/qdrant.log`

---

## 🚨 Troubleshooting

### Common Issues

**Q: "Backend server did not start"**
- A: Check if port 8000 is in use: `netstat -ano | findstr :8000`
- Kill the process or change port in `src-tauri/src/main.rs`

**Q: "Database connection refused"**
- A: PostgreSQL executable failed to start
- Check `data/postgres/postgresql.log` for errors
- Delete `data/postgres/` and restart (recreates fresh database)

**Q: "Qdrant connection refused"**
- A: Similarly, delete `src-tauri/resources/qdrant/` and restart

**Q: "Windows Defender blocks the app"**
- A: This is normal for new unsigned apps
- Click "More info" → "Run anyway"
- Binary is compiled locally, completely safe

**Q: "Models not downloading"**
- A: Check internet connection
- Models download on first query (Ctrl+Shift+I shows console)
- Large files (500MB-1GB), may take 5-10 minutes

---

## 🔐 Security & Privacy

### Local-First Design
- **Zero cloud** - All data processed locally
- **No telemetry** - No tracking or phone home
- **No API calls** - Except optional HuggingFace for model downloads
- **Isolated processes** - Each sidecar runs with minimal privileges
- **No network access** - Backend listens on `127.0.0.1` only (localhost)

### Data Storage
```
Windows:  %APPDATA%\Atlas\data\
Linux:    ~/.atlas/data/
macOS:    ~/Library/Application Support/Atlas/data/
```

All databases (PostgreSQL, Qdrant) store data in the local app data folder. Encrypted storage coming in v2.1.

---

## 📊 Model Information

### Included Models

**LLaMA 2 (7B)** - Local inference
- ~4GB RAM required
- Fast responses (~2-5 sec per query)
- No internet needed

**Nomic Embed Text** - Embeddings
- ~350MB
- Runs locally via sentence-transformers
- No external API calls

**GLiNER** - Named Entity Recognition
- Fast, lightweight (~50MB)
- No hallucinations (unlike LLM-based NER)
- ~50x faster than LLM extraction

**Changelog:**
- v2.0: LLaMA switched from Ollama → llama-cpp-python (bundled)
- v2.1 (planned): Quantized models for faster inference
- v2.2 (planned): GPU acceleration (CUDA) for RTX cards

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Tips
- **File issues** for bugs or feature requests
- **Pull requests** with tests for new features
- **Performance improvements** especially welcome (see Performance section)

### Key Areas for Contribution
1. Relationship extraction improvements (currently semantic-only)
2. Better entity linking (cross-document entity resolution)
3. Graph visualization enhancements
4. Additional model support (different embeddings, LLMs)
5. Documentation and tutorials

---

## 📚 References

- **Tauri** - Desktop app framework: https://tauri.app/
- **PyInstaller** - Python bundling: https://pyinstaller.org/
- **Qdrant** - Vector database: https://qdrant.tech/
- **PostgreSQL** - Relational database: https://www.postgresql.org/
- **FastAPI** - Python web framework: https://fastapi.tiangolo.com/
- **Next.js** - React framework: https://nextjs.org/
- **GLiNER** - NER model: https://github.com/talipmoon/gliner

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🎓 What is Atlas?

Atlas is designed for researchers, analysts, and knowledge workers who need to:
- Build queryable knowledge bases from unstructured documents
- Discover non-obvious connections and relationships
- Get answers grounded in source documents (not hallucinations)
- Maintain full data privacy and control

**Unlike traditional RAG systems**, Atlas:
- ✅ Explicitly extracts and stores relationships (not just embeddings)
- ✅ Queries in multiple modalities (vectors, text, graph, semantic)
- ✅ Explains its reasoning (transparent answer generation)
- ✅ Runs entirely locally with no external dependencies
- ✅ Handles incremental ingestion and updates efficiently

---

## 🐛 Bug Reports & Support

Found a bug? Have a feature request?

- **GitHub Issues**: https://github.com/[your-repo]/atlas/issues
- **Discussions**: https://github.com/[your-repo]/atlas/discussions
- **Email**: support@[your-org]

---

**Last Updated:** January 2025
**Version:** 2.0.0
**Status:** Production Ready ✅

---

## 🚀 Quick Start

### Prerequisites

1. **Docker Desktop** (for Windows/Mac) or Docker Engine (for Linux)
2. **Ollama** - Download from https://ollama.ai
3. **Node.js 18+** - For frontend development
4. **Python 3.9+** - For backend

### Required Models

```bash
# Pull the Llama3 model (for chat and query synthesis)
ollama pull llama3

# Pull the embedding model
ollama pull nomic-embed-text
```

**Note:** Entity extraction uses GLiNER (automatically downloaded on first use), not Ollama.

### Step 1: Start Database Services

**Open PowerShell** in the project folder:

```powershell
docker-compose up -d db_graph db_vector
```

Wait 10-15 seconds, then verify they're running:

```powershell
docker-compose ps
```

You should see both `atlas-postgres` and `atlas-qdrant` with status "Up".

### Step 2: Start Backend Server

**Open a NEW PowerShell window** and run:

```powershell
# Navigate to backend
cd backend

# Activate virtual environment (if using one)
.\.venv\Scripts\Activate.ps1

# Set environment variables
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "atlas_knowledge"
$env:POSTGRES_USER = "atlas"
$env:POSTGRES_PASSWORD = "atlas_secure_password"
$env:QDRANT_HOST = "localhost"
$env:QDRANT_PORT = "6333"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
$env:UPLOAD_DIR = "./data/uploads"

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**You should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
✓ Database initialized
```

**✅ Keep this window open!** The backend is now running.

**Test it:** Open http://localhost:8000/health in your browser

### Step 3: Start Frontend

**Open ANOTHER NEW PowerShell window** and run:

```powershell
# Navigate to frontend
cd frontend

# Start Next.js
npm run dev
```

**You should see:**
```
  ▲ Next.js 14.1.0
  - Local:        http://localhost:3000
```

**✅ Keep this window open too!** The frontend is now running.

### Step 4: Open the Application

**Open your browser** and go to: **http://localhost:3000**

---

## 🖥️ Standalone desktop build (no Docker)

You can build a **fully standalone** desktop app so you don't need Docker, Rancher, or a manual Python server:

1. **Backend (required):** Build the Python backend as a single exe and place it for Tauri:
   ```powershell
   .\build-backend.ps1
   ```
   This runs PyInstaller (`backend/atlas.spec`) and copies the exe to `src-tauri/binaries/atlas-backend-x86_64-pc-windows-msvc.exe`.

2. **PostgreSQL + Qdrant (optional):** To bundle Postgres and Qdrant so the app starts them itself:
   ```powershell
   .\scripts\download-bundle-resources.ps1
   ```
   Downloads binaries into `src-tauri/resources/`. If you skip this, the app still runs but expects Postgres and Qdrant to be running elsewhere.

3. **Build the app:**
   ```powershell
   npm run tauri:build
   ```
   (Or `npm run build:backend` then `npx tauri build`.)

**Startup:** When resources are present, the app starts Postgres → Qdrant → Backend automatically and stops them on exit. See `src-tauri/resources/README.md` for details.

---

## 📊 Example Queries

### Upload a Document

**Via API:**
```bash
curl -X POST "http://localhost:8000/ingest" -F "file=@document.pdf"
```

**Via Frontend:**
1. Navigate to http://localhost:3000
2. Click "Upload Document"
3. Select PDF file
4. Processing happens in the background - check status via `/files` endpoint

### Ask a Question

**Via API:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What experimental methods are used?"}'
```

**Via Frontend:**
- Type query in the chat interface
- View retrieved chunks, entities, and relationships
- Explore knowledge graph visualization

### Find Relationships

```bash
curl "http://localhost:8000/entities/{entity_id}/relationships?direction=both"
```

### List Documents

```bash
curl "http://localhost:8000/files"
```

### Get Knowledge Graph

```bash
curl "http://localhost:8000/graph/full?document_id={doc_id}"
```

---

## 🏗️ Architecture

### Knowledge Layer (3 Components)

1. **Vector Store (Qdrant)**
   - Semantic search over document chunks
   - Metadata filtering
   - Top-K retrieval
   - Embeddings via Ollama (nomic-embed-text)

2. **Knowledge Graph (PostgreSQL)**
   - Entities (chemicals, experiments, concepts)
   - Relationships (co-occurrence, causation, etc.)
   - Path finding and context expansion
   - Flexible JSONB properties

3. **Document Store (PostgreSQL)**
   - Original documents
   - Chunks with provenance
   - Deduplication via SHA256 hashing
   - Status tracking (pending, processing, completed, failed)

### Processing Pipeline

**Ingestion** (Async & Parallelized):
1. Extract text from PDF (async)
2. Chunk with overlap
3. Store chunks in PostgreSQL
4. **Parallel** entity extraction using GLiNER (fast BERT-based NER)
5. **Parallel** embedding generation
6. Store embeddings in Qdrant
7. Create graph nodes and relationships (only for nearby entities)
8. Mark as completed

**Query**:
1. Semantic search (Qdrant) - top 5 chunks
2. Extract node_ids from chunks
3. Expand via knowledge graph (1-hop neighborhood)
4. Synthesize answer with LLM (Ollama)
5. Return answer + reasoning + citations

---

## 📁 Project Structure

```
Atlas2.0/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── api/
│   │   │   └── routes.py        # API endpoints
│   │   ├── core/
│   │   │   ├── config.py        # Configuration
│   │   │   └── database.py     # PostgreSQL schema
│   │   └── services/
│   │       ├── chat.py          # Chat service
│   │       ├── ingest.py        # Ingestion pipeline (async)
│   │       ├── document.py      # Document management
│   │       ├── graph.py         # Graph operations
│   │       └── retrieval.py     # Hybrid RAG retrieval
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/                     # Next.js pages
│   ├── components/              # React components
│   └── lib/                     # Utilities
├── data/
│   ├── postgres/                # PostgreSQL data
│   ├── qdrant/                  # Qdrant data
│   └── uploads/                 # PDF files
└── README.md                    # This file
```

---

## 🔧 Technology Stack

| Component | Technology |
|-----------|-----------|
| Vector Store | Qdrant |
| Knowledge Graph | PostgreSQL + SQLAlchemy |
| Document Store | PostgreSQL |
| LLM | Ollama (llama3) |
| Embeddings | nomic-embed-text |
| NER | GLiNER (urchade/gliner_small-v2.1) |
| Backend API | FastAPI (async) |
| Frontend | Next.js + React |
| Infrastructure | Docker Compose (PostgreSQL + Qdrant) |

---

## 🛠️ Recent Improvements (Refactor 2026)

### Performance Optimizations
- ✅ **Async Ingestion**: Document processing is now fully asynchronous
- ✅ **Parallel Entity Extraction**: Multiple chunks processed concurrently using `asyncio.gather`
- ✅ **Parallel Embedding**: All chunk embeddings generated in parallel
- ✅ **Background Tasks**: `/ingest` endpoint returns immediately, processing happens in background
- ✅ **GLiNER NER**: Replaced slow LLM-based NER with fast GLiNER extraction (~50x faster, no hallucinations)
- ✅ **Smart Graph Construction**: Only creates edges for entities within 100 characters (prevents "hairball" graphs)
- ✅ **Progress Tracking**: Real-time progress updates during ingestion (total_chunks, processed_chunks)

### Code Quality
- ✅ **Dependency Injection**: Replaced global service variables with FastAPI `Depends()`
- ✅ **Better Error Handling**: Improved session management and rollback on errors
- ✅ **Removed Legacy Code**: Deleted redundant `backend/server.py`
- ✅ **Session Management**: Fixed potential session leaks and race conditions

### Architecture
- ✅ **Non-blocking API**: Large file uploads no longer cause HTTP timeouts
- ✅ **Testable Code**: Services can now be easily mocked for testing
- ✅ **Cleaner Dependencies**: Services initialized per-request via DI

---

## 🐛 Troubleshooting

### Backend Issues

**Container won't start:**
```bash
docker-compose logs app
```

**Database connection errors:**
```bash
# Check if PostgreSQL is healthy
docker ps
# Restart services
docker-compose restart
```

**Ollama connection refused:**
- Verify Ollama is running: `ollama list`
- Check firewall isn't blocking port 11434
- On Linux: Change `OLLAMA_BASE_URL` to `http://localhost:11434`

**GLiNER model not found:**
GLiNER automatically downloads the model (`urchade/gliner_small-v2.1`) on first use. If you encounter issues:
```bash
# Ensure torch is installed
pip install torch gliner
```

### Frontend Issues

**Port 3000 not responding:**
```bash
# Clear Next.js cache
rm -rf frontend/.next
cd frontend
npm run dev
```

**API calls failing:**
- Check backend is running on port 8000
- Verify CORS is configured in backend

### Model Issues

**Poor entity extraction:**
- GLiNER automatically downloads on first use - check logs for "✅ Loaded GLiNER model"
- Verify GLiNER is installed: `pip show gliner`
- Check that torch is installed: `pip show torch`
- GLiNER uses labels: Person, Organization, Location, Concept, Method, Chemical

**Slow responses:**
- LLM inference is CPU/GPU intensive
- Consider using smaller model for testing
- Check Ollama logs: `ollama logs`

---

## 📖 API Documentation

### Core Endpoints

- `GET /` - Health check
- `GET /health` - Comprehensive health check
- `POST /chat` - Query with natural language
- `POST /ingest` - Upload PDF document (background processing)
- `GET /files` - List uploaded documents
- `GET /files/{doc_id}` - Get document file
- `DELETE /files/{doc_id}` - Delete document

### Graph Endpoints

- `GET /entities` - List entities (nodes)
- `GET /entities/{entity_id}/relationships` - Get entity relationships
- `GET /graph/types` - Get entity types with counts
- `GET /graph/full` - Get complete graph (nodes + edges)

### Interactive API Docs

When the backend is running, visit: **http://localhost:8000/docs**

---

## 🎯 Success Criteria

This system is successful if:

- ✅ Neo4j is completely removed
- ✅ Knowledge layer is separate from AI
- ✅ System explains reasoning
- ✅ Relationships are queryable independently
- ✅ Architecture scales conceptually
- ✅ Fully open source
- ✅ Non-blocking ingestion
- ✅ Fast entity extraction

---

## 🛠️ Development Status

**Current Phase**: Production-Ready MVP

### Implemented
- ✅ Full knowledge layer (3 components)
- ✅ Async document ingestion pipeline
- ✅ Parallel entity extraction (GLiNER - fast BERT-based NER)
- ✅ Query orchestration
- ✅ Relationship tracking (smart proximity-based edge creation)
- ✅ Transparent reasoning
- ✅ Background task processing
- ✅ FastAPI Dependency Injection
- ✅ Real-time progress tracking for document ingestion

### Future Enhancements (Local-First Roadmap)

**Core Functionality:**
- 🔍 **Advanced Search**: Full-text search across documents with boolean operators, date ranges, and field-specific queries
- 📊 **Multi-Document Comparison**: Side-by-side analysis of concepts, methods, and findings across multiple papers
- 🔗 **Relationship Type Inference**: Automatically classify edge types (causes, uses, references, contradicts) using local LLM
- 📑 **Citation Manager**: Export citations in BibTeX, APA, MLA formats with clickable links to source pages
- 🗺️ **Interactive Graph Explorer**: Enhanced visualization with filtering, clustering, and path-finding between entities

**Performance & Scalability:**
- ⚡ **Embedded Database Mode**: SQLite option for single-user deployments (no PostgreSQL required)
- 🚀 **Incremental Indexing**: Only re-process changed pages when documents are updated
- 💾 **Local Model Caching**: Pre-download and cache GLiNER/Ollama models for offline-first operation
- 🔄 **Smart Deduplication**: Detect and merge duplicate entities across documents automatically
- 📦 **Batch Import**: Process entire directories of PDFs with progress tracking and error recovery

**Desktop App Packaging:**
- 🖥️ **Electron/Tauri Wrapper**: Package as native desktop app (Windows/Mac/Linux)
- 📱 **Single Executable**: Self-contained binary with embedded databases and models
- 🔒 **Local Data Encryption**: Optional encryption at rest for sensitive documents
- ⚙️ **Settings UI**: Graphical configuration panel instead of editing .env files
- 🔔 **System Notifications**: Desktop notifications for completed ingestion and errors

**User Experience:**
- 🎨 **Dark Mode**: Full dark theme support for extended reading sessions
- 📝 **Annotation System**: Highlight and annotate PDFs with notes linked to knowledge graph
- 🔖 **Bookmarks & Collections**: Organize documents into custom collections with tags
- 📈 **Analytics Dashboard**: Visualize document statistics, entity counts, and query patterns
- 🔍 **Query History**: Save and replay previous queries with context

**Advanced Features:**
- 🤖 **Multi-Hop Reasoning**: Follow relationship chains (A→B→C) to answer complex questions
- 📚 **Document Summarization**: Auto-generate summaries using local LLM with key entities highlighted
- 🔄 **Version Control**: Track document versions and changes over time
- 🌐 **Multi-Language Support**: Extend GLiNER to extract entities in multiple languages
- 🧪 **Query Templates**: Pre-built query templates for common research questions
- OCR Implemntation for non textbased documents and images like lab notebooks. 

---

## 🔧 Configuration

### Backend Environment Variables

Located in `backend/app/core/config.py` or `.env`:

```python
POSTGRES_HOST = "localhost"  # or "db_graph" for Docker
POSTGRES_PORT = 5432
POSTGRES_DB = "atlas_knowledge"
POSTGRES_USER = "atlas"
POSTGRES_PASSWORD = "atlas_secure_password"

QDRANT_HOST = "localhost"  # or "db_vector" for Docker
QDRANT_PORT = 6333

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"

UPLOAD_DIR = "./data/uploads"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K_RETRIEVAL = 5
```

---

## 📝 Example Queries

After uploading research papers:

- "What methodology was used in this study?"
- "List all chemicals mentioned in the experiments"
- "What were the main conclusions?"
- "Show relationships between entities X and Y"
- "Compare the methods used in different papers"

---

## 🤝 Contributing

Contributions welcome! This is a systems project focused on:

- **Correctness over convenience**
- **Simplicity over feature creep**
- **Clear separation of concerns**
- **Performance and scalability**

---

## 📝 License

[Your License Here]

---

## 📧 Contact

[Your Contact Information]

---

## 🙏 Acknowledgments

Built on the principle that **AI should query knowledge, not pretend to have it**.

Inspired by the need for transparent, explainable, and grounded AI systems.
