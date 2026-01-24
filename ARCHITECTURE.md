# Atlas 2.0 - AI-Native Knowledge Layer

## Architecture Overview

Atlas 2.0 is a **continuous knowledge layer** designed to sit beneath an AI model, replacing traditional approaches with a fully open-source, scalable architecture optimized for retrieval, relationships, and reasoning over documents.

### Core Principle

> **The AI does not know things. It queries a living knowledge substrate.**

This system is not a chatbot - it's a knowledge layer that makes AI reasoning transparent, explainable, and grounded in actual documents.

---

## System Architecture

```
┌─────────────────────────────────────────────────┐
│              USER QUERY                          │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│     LIGHTWEIGHT LLM (Ollama - 1B params)        │
│     (Probe to test knowledge layer)             │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│        RETRIEVAL ORCHESTRATOR                    │
│  (Coordinates across knowledge layers)          │
└──────────────────┬──────────────────────────────┘
                   ↓
    ┌──────────────┴──────────────┐
    │    KNOWLEDGE LAYER           │
    │  (3 Separate Components)     │
    └──────────────┬──────────────┘
                   ↓
    ┌──────────────────────────────┐
    │                              │
    ↓                              ↓
┌─────────────┐  ┌──────────────────┐  ┌─────────────┐
│   QDRANT    │  │   POSTGRESQL     │  │ POSTGRESQL  │
│ Vector Store│  │ Knowledge Graph  │  │ Doc Store   │
│             │  │                  │  │             │
│ • Embeddings│  │ • Entities       │  │ • Documents │
│ • Semantic  │  │ • Relationships  │  │ • Chunks    │
│   search    │  │ • Graph queries  │  │ • Metadata  │
└─────────────┘  └──────────────────┘  └─────────────┘
```

---

## Key Changes from 1.0

### ❌ REMOVED (Completely)
- **Neo4j** - No longer used
- **ChromaDB** - Replaced with Qdrant
- **LangChain** - Removed abstraction layer
- **Tight AI-DB coupling** - Clear separation of concerns

### ✅ NEW ARCHITECTURE
1. **Qdrant** - Production-ready vector store
2. **PostgreSQL** - Unified backend for both:
   - Knowledge graph (entities + relationships)
   - Document store (raw docs + chunks)
3. **Clear Module Separation** - Each layer is independent
4. **Idempotent Ingestion** - Can re-process documents safely
5. **Reasoning Transparency** - System explains why it gives answers

---

## Technology Stack

### Knowledge Layer
- **Vector Store**: Qdrant (semantic search)
- **Knowledge Graph**: PostgreSQL + SQLAlchemy (relationships)
- **Document Store**: PostgreSQL (ground truth)

### AI / Processing
- **LLM**: Ollama (llama3.2:1b - local, small model for testing)
- **Embeddings**: nomic-embed-text (via Ollama)
- **Entity Extraction**: LLM-based + regex fallback

### Infrastructure
- **Backend**: FastAPI + Python 3.9+
- **Database**: PostgreSQL 16
- **Runtime**: Local services (PostgreSQL + Qdrant) or SQLite/local vectors fallback
- **Frontend**: Next.js + React + TypeScript

---

## Module Descriptions

### 1. Vector Store (`vector_store.py`)
**Purpose**: Semantic retrieval of document chunks

**Responsibilities**:
- Store embeddings for document chunks
- Fast top-K similarity search
- Metadata filtering (by document, page, etc.)

**Key Methods**:
- `add_chunks()` - Store embedded chunks
- `search()` - Semantic search with filters
- `delete_document()` - Remove all chunks for a doc

### 2. Knowledge Graph (`knowledge_graph.py`)
**Purpose**: Relationship tracking and expansion

**Responsibilities**:
- Store entities (people, chemicals, concepts, etc.)
- Track relationships between entities
- Graph traversal and path finding
- Context expansion for queries

**Key Methods**:
- `add_entity()` - Create entity node
- `add_relationship()` - Create edge between entities
- `find_path()` - Find connections between entities
- `expand_context()` - Get related entities for reasoning

### 3. Document Store (`document_store.py`)
**Purpose**: Ground truth and provenance

**Responsibilities**:
- Store original documents
- Manage chunks with metadata
- Deduplication via file hashing
- Track processing status

**Key Methods**:
- `add_document()` - Store new document (with dedup check)
- `add_chunks()` - Store document chunks
- `get_document()` - Retrieve document info
- `delete_document()` - Remove document and chunks

### 4. Ingestion Pipeline (`ingest.py`)
**Purpose**: Process documents through all layers

**Pipeline Steps**:
1. Extract text from PDF
2. Chunk document with overlap
3. Store in document store
4. Embed chunks → Qdrant
5. Extract entities → Knowledge graph
6. Create co-occurrence relationships

**Idempotent**: Can run multiple times on same document

### 5. Query Orchestrator (`query_orchestrator.py`)
**Purpose**: Coordinate retrieval and reasoning

**Query Pipeline**:
1. Semantic search in vector store
2. Extract entities from results
3. Expand context via knowledge graph
4. Retrieve supporting documents
5. Synthesize answer with LLM
6. Return answer + citations + reasoning

**Query Types Supported**:
- General questions
- Relationship queries ("How are X and Y connected?")
- Document-specific questions
- Concept search ("Which documents mention X?")

### 6. API Server (`server.py`)
**Purpose**: FastAPI REST interface

**Endpoints**:
- `POST /ingest` - Upload and process documents
- `POST /chat` - Query the knowledge layer
- `GET /files` - List documents
- `GET /entities` - Explore knowledge graph
- `GET /stats` - System statistics

---

## Database Schema

### Documents Table
```sql
- id (UUID)
- filename
- file_hash (SHA256 for deduplication)
- file_path
- file_size
- mime_type
- uploaded_at
- processed_at
- status (pending, processing, completed, failed)
- metadata (JSON)
```

### Document Chunks Table
```sql
- id (chunk_id)
- document_id (FK)
- text
- chunk_index
- page_number
- start_char, end_char
- metadata (JSON)
```

### Entities Table (Knowledge Graph)
```sql
- id (UUID)
- name
- entity_type (chemical, experiment, concept, etc.)
- description
- document_id (FK)
- chunk_id (FK)
- page_number
- properties (JSON)
- confidence
- extracted_at
```

### Relationships Table (Knowledge Graph)
```sql
- id (UUID)
- source_id (FK to entities)
- target_id (FK to entities)
- relationship_type
- context (text snippet)
- document_id (FK)
- properties (JSON)
- confidence
- created_at
```

---

## Scaling Considerations

This MVP architecture scales conceptually to millions of documents:

1. **Vector Store**: Qdrant supports billions of vectors with sharding
2. **PostgreSQL**: Can handle TB-scale with partitioning
3. **Horizontal Scaling**: Each layer can scale independently
4. **Caching**: Can add Redis layer for hot queries
5. **Async Processing**: Ingestion can be background queued

---

## Development Roadmap

### Phase 1: MVP (Current)
- ✅ Remove Neo4j
- ✅ Implement 3-layer knowledge substrate
- ✅ Basic entity extraction
- ✅ Query orchestration
- ✅ Example queries

### Phase 2: Enhancement
- Advanced entity extraction (NER models)
- Relationship type inference
- Multi-hop reasoning
- Query optimization
- Batch processing

### Phase 3: Production
- Authentication & authorization
- Rate limiting
- Monitoring & observability
- Backup & recovery
- Performance tuning

---

## Success Criteria

This system is successful if:

1. ✅ **Neo4j is completely removed**
2. ✅ **Knowledge layer is clearly separate from AI**
3. ✅ **System can explain why an answer is given**
4. ✅ **Relationships are queryable independently of embeddings**
5. ✅ **Architecture scales conceptually beyond this MVP**
6. ✅ **Fully open source stack**

---

## Contributing

This is a systems MVP focused on architecture, not a production product.

Key principles:
- **Correctness over convenience**
- **Simplicity over feature creep**
- **Clear separation of layers**
