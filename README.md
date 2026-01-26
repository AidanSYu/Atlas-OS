# Atlas 2.0 - AI-Native Knowledge Layer

> **The AI does not know things. It queries a living knowledge substrate.**

Atlas 2.0 is a complete rewrite focused on building a **continuous knowledge layer** beneath an AI model. This is not a chatbot - it's a scalable, explainable, open-source knowledge substrate optimized for retrieval, relationships, and reasoning over documents.

---

## 🎯 What Changed?

### ❌ Removed
- **Neo4j** - Completely removed
- **ChromaDB** - Replaced with Qdrant
- **LangChain** - Direct integrations instead
- **Tight AI-Graph coupling** - Clear layer separation

### ✅ New Architecture
```
User Query
    ↓
Lightweight LLM (Ollama)
    ↓
Retrieval Orchestrator
    ↓
┌─────────────────────────────┐
│   Knowledge Layer (3 parts) │
├─────────────────────────────┤
│ 1. Qdrant (Vector Store)    │
│ 2. PostgreSQL (Graph)       │
│ 3. PostgreSQL (Doc Store)   │
└─────────────────────────────┘
```

---

## ✨ Key Features

1. **Transparent Reasoning** - System explains *why* it gives each answer
2. **Relationship Queries** - Ask "How are X and Y connected?"
3. **Document Grounding** - All answers cite source documents and pages
4. **Knowledge Graph** - Entities and relationships queryable independently
5. **Idempotent Ingestion** - Safe to reprocess documents
6. **Fully Open Source** - No proprietary components
7. **Async Processing** - Non-blocking document ingestion with background tasks
8. **Fast NER** - GLiNER-based entity extraction (~50x faster than LLM, no hallucinations)

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
