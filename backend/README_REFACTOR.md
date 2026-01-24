# Atlas Refactored Architecture

## Overview

This refactored codebase implements a clean **Hexagonal Architecture** with a flexible **Triple Store** schema for the knowledge graph.

## Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration settings
│   │   └── database.py          # Triple Store models (Node/Edge with JSONB)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingest.py           # Document ingestion pipeline
│   │   ├── retrieval.py        # Hybrid RAG retrieval (CRITICAL FIX)
│   │   └── chat.py             # Chat service interface
│   └── api/
│       ├── __init__.py
│       └── routes.py            # FastAPI route handlers
├── Dockerfile
└── requirements.txt
```

## Key Changes

### 1. Triple Store Schema

**Old:** Rigid tables (Entity, Relationship with fixed columns)
**New:** Flexible Triple Store:
- `nodes` table: `id` (UUID), `label` (String), `properties` (JSONB)
- `edges` table: `id` (UUID), `source_id`, `target_id`, `type` (String), `properties` (JSONB)
- GIN indices on JSONB columns for fast filtering

### 2. Fixed Retrieval Logic

The critical fix in `retrieval.py`:

1. **Vector Step:** Query Qdrant for top 5 text chunks
2. **Graph Expansion Step:**
   - Extract `node_ids` from Qdrant payload metadata
   - Query PostgreSQL for 1-hop neighborhood of those nodes
3. **Synthesis Step:** Format vector text + graph facts into prompt
4. **Generation:** Send context to Ollama

### 3. OCI-Standard Docker Compose

The `docker-compose.yml` uses only standard OCI configuration:
- No Docker Desktop extensions
- Compatible with Podman and Rancher Desktop
- Services: `db_graph` (PostgreSQL), `db_vector` (Qdrant), `app` (FastAPI)

## Running the Application

### With Docker Compose

```bash
docker-compose up -d
```

The app will be available at `http://localhost:8000`

### Local Development

1. Ensure PostgreSQL and Qdrant are running (or use docker-compose for just those services)
2. Set environment variables or use `.env` file
3. Run:
```bash
cd backend
uvicorn app.main:app --reload
```

## API Endpoints

- `GET /` - Health check
- `GET /health` - Service health status
- `POST /chat` - Query the knowledge layer (main endpoint)
- `POST /ingest` - Upload and process PDF documents

## Environment Variables

See `app/core/config.py` for all configuration options. Key variables:
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL`

## Migration Notes

The old codebase used:
- `database.py` with Entity/Relationship models
- `query_orchestrator.py` for retrieval
- `server.py` for API routes

The new structure separates concerns:
- **Core:** Configuration and database models
- **Services:** Business logic (ingestion, retrieval, chat)
- **API:** Route handlers only
