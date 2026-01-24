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
Lightweight LLM (Ollama 1B)
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

---

## 🚀 Quick Start

docker-compose up -d
### Prerequisites (docker-free)
- Python 3.9+
- PostgreSQL running locally on `localhost:5432` (or set `DB_BACKEND=sqlite`)
- Qdrant running locally on `localhost:6333` (or set `VECTOR_BACKEND=local`)
- Ollama

### Start in 4 Commands

```bash
# 1. Install models (once)
ollama pull llama3.2:1b && ollama pull nomic-embed-text

# 2. Set env for local dev (optional fallbacks)
cd backend
cp .env.example .env  # if missing
set DB_BACKEND=sqlite
set VECTOR_BACKEND=local

# 3. Start backend
pip install -r requirements.txt && python server.py

# 4. Start frontend (new terminal)
cd ../frontend && npm install && npm run dev
```

**Server**: http://localhost:8000  
**API Docs**: http://localhost:8000/docs
**Frontend**: http://localhost:3000

See [QUICKSTART.md](QUICKSTART.md) for detailed setup.

---

## 📊 Example Queries

### Upload a Document
```bash
curl -X POST "http://localhost:8000/ingest" -F "file=@paper.pdf"
```

### Ask a Question
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What experimental methods are used?"}'
```

### Find Relationships
```bash
curl "http://localhost:8000/query/relationship?entity1=catalyst&entity2=reaction"
```

### Search Documents
```bash
curl "http://localhost:8000/query/search?concept=photocatalysis"
```

---

## 🏗️ Architecture

### Knowledge Layer (3 Components)

1. **Vector Store (Qdrant)**
   - Semantic search over document chunks
   - Metadata filtering
   - Top-K retrieval

2. **Knowledge Graph (PostgreSQL)**
   - Entities (chemicals, experiments, concepts)
   - Relationships (co-occurrence, causation, etc.)
   - Path finding and context expansion

3. **Document Store (PostgreSQL)**
   - Original documents
   - Chunks with provenance
   - Deduplication via hashing

### Processing Pipeline

**Ingestion**:
1. Extract text from PDF
2. Chunk with overlap
3. Embed → Qdrant
4. Extract entities → Graph
5. Create relationships

**Query**:
1. Semantic search (Qdrant)
2. Extract entities
3. Expand via graph
4. Retrieve documents
5. Synthesize with LLM
6. Return answer + reasoning + citations

---

## 📁 Project Structure

```
Atlas2.0/
├── backend/
│   ├── server.py              # FastAPI server
│   ├── config.py              # Configuration
│   ├── database.py            # PostgreSQL schema
│   ├── vector_store.py        # Qdrant integration
│   ├── knowledge_graph.py     # Graph operations
│   ├── document_store.py      # Document management
│   ├── ingest.py              # Ingestion pipeline
│   ├── query_orchestrator.py # Query coordination
│   └── requirements.txt
├── frontend/
│   ├── app/                   # Next.js app
│   ├── components/            # React components
│   └── lib/                   # Utilities
├── data/
│   ├── postgres/              # PostgreSQL data
│   ├── qdrant/                # Qdrant data
│   └── uploads/               # PDF files
├── ARCHITECTURE.md            # Detailed design docs
├── QUICKSTART.md              # Setup guide
└── README.md                  # This file
```

---

## 🔧 Technology Stack

| Component | Technology |
|-----------|-----------|
| Vector Store | Qdrant |
| Knowledge Graph | PostgreSQL + SQLAlchemy |
| Document Store | PostgreSQL |
| LLM | Ollama (llama3.2:1b) |
| Embeddings | nomic-embed-text |
| Backend API | FastAPI |
| Frontend | Next.js + React |
| Infrastructure | Local services (PostgreSQL + Qdrant) or SQLite/local vectors fallback |

---

## 📖 Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed architecture and design decisions
- [QUICKSTART.md](QUICKSTART.md) - Setup and configuration guide
- [API Documentation](http://localhost:8000/docs) - Interactive API docs (when running)

---

## 🎯 Success Criteria

This system is successful if:

- ✅ Neo4j is completely removed
- ✅ Knowledge layer is separate from AI
- ✅ System explains reasoning
- ✅ Relationships are queryable independently
- ✅ Architecture scales conceptually
- ✅ Fully open source

---

## 🛠️ Development Status

**Current Phase**: MVP (Minimum Viable Product)

This is a **systems MVP** focused on architecture, not a production product.

### Implemented
- ✅ Full knowledge layer (3 components)
- ✅ Document ingestion pipeline
- ✅ Query orchestration
- ✅ Entity extraction
- ✅ Relationship tracking
- ✅ Transparent reasoning

### Future Enhancements
- Advanced NER models
- Relationship type inference
- Multi-hop reasoning optimization
- Background processing
- Authentication
- Monitoring & observability

---

## 🤝 Contributing

Contributions welcome! This is a systems project focused on:

- **Correctness over convenience**
- **Simplicity over feature creep**
- **Clear separation of concerns**

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
