# Atlas 2.0 - AI-Native Knowledge Layer

Complete guide for running and using Atlas 2.0.

## System Overview

Atlas is a scalable knowledge substrate for AI applications that combines:
- **PostgreSQL** - Knowledge graph storage (nodes & edges)
- **Qdrant** - Vector embeddings for semantic search
- **Ollama** - Local LLM inference (llama3 8B model)
- **FastAPI** - Backend REST API
- **Next.js** - Frontend interface

## Prerequisites

### Required Software
1. **Docker Desktop** (for Windows/Mac) or Docker Engine (for Linux)
2. **Ollama** - Download from https://ollama.ai
3. **Node.js 18+** - For frontend development

### Required Models
```bash
# Pull the Llama3 8B model (for chat and entity extraction)
ollama pull llama3

# Pull the embedding model
ollama pull nomic-embed-text
```

## Quick Start

### 1. Start Backend Services (Docker)

```bash
cd ContAInnum_Atlas2.0_backup_20260124_181415
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- Qdrant on ports 6333 (HTTP) & 6334 (gRPC)
- FastAPI backend on port 8000

**Verify backend is running:**
```bash
curl http://localhost:8000/health
```

### 2. Start Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: http://localhost:3000

## Configuration

### Backend Environment Variables

Located in `docker-compose.yml`:

```yaml
OLLAMA_BASE_URL: http://host.docker.internal:11434  # For Docker Desktop on Windows/Mac
OLLAMA_MODEL: llama3                                 # 8B model for better results
POSTGRES_HOST: db_graph
QDRANT_HOST: db_vector
```

### Key Configuration Changes

**Fixed Issues:**
1. ✅ Changed `OLLAMA_BASE_URL` from `localhost` to `host.docker.internal` (Docker networking)
2. ✅ Upgraded model from `llama3.2:1b` to `llama3` (8B for better entity extraction)
3. ✅ Removed 10-chunk processing limit in ingestion
4. ✅ Fixed Qdrant volume mounting for Windows compatibility

## Usage

### Upload Documents

**Via API:**
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@document.pdf"
```

**Via Frontend:**
1. Navigate to http://localhost:3000
2. Click "Upload Document"
3. Select PDF file
4. Wait for ingestion to complete

### Query Knowledge

**Via API:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What chemicals were used in the experiment?"}'
```

**Via Frontend:**
- Type query in the chat interface
- View retrieved chunks, entities, and relationships
- Explore knowledge graph visualization

### Check System Health

```bash
curl http://localhost:8000/health
```

Returns status of all services (API, Qdrant, PostgreSQL, Ollama).

## API Endpoints

### Core Endpoints
- `GET /health` - System health check
- `POST /upload` - Upload PDF document
- `POST /chat` - Query with natural language
- `GET /documents` - List uploaded documents
- `DELETE /documents/{doc_id}` - Delete document

### Graph Endpoints
- `GET /graph/nodes` - Get all nodes
- `GET /graph/edges` - Get all edges
- `GET /graph/search?query=...` - Search graph by node name

## Architecture

```
┌─────────────┐
│  Next.js    │ :3000
│  Frontend   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  FastAPI    │ :8000
│  Backend    │
└──┬───┬───┬──┘
   │   │   │
   ▼   ▼   ▼
┌────┐┌────┐┌────┐
│PG  ││Qdr ││Oll │
│SQL ││ant ││ama │
└────┘└────┘└────┘
```

### Data Flow

1. **Ingestion**: PDF → Text → Chunks → Embeddings → Qdrant + Entities → PostgreSQL
2. **Retrieval**: Query → Embedding → Vector Search (Qdrant) → Get Nodes (PostgreSQL)
3. **Response**: LLM generates answer using retrieved context

## Troubleshooting

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
- Ensure you're using `llama3` (8B), not `llama3.2:1b`
- Verify with: `ollama list`

**Slow responses:**
- LLM inference is CPU/GPU intensive
- Consider using smaller model for testing
- Check Ollama logs: `ollama logs`

## Development

### Backend Structure
```
backend/
├── app/
│   ├── api/        # FastAPI routes
│   ├── core/       # Config, database
│   └── services/   # Business logic
├── Dockerfile
└── requirements.txt
```

### Frontend Structure
```
frontend/
├── app/            # Next.js pages
├── components/     # React components
└── lib/            # API client, utilities
```

### Running Tests

**Backend:**
```bash
cd backend
pytest
```

**Frontend:**
```bash
cd frontend
npm test
```

## Maintenance

### Clear All Data

```bash
# Stop containers
docker-compose down

# Remove volumes (⚠️ deletes all data)
docker volume rm containnum_atlas20_backup_20260124_181415_qdrant_data
rm -rf data/postgres/*
```

### Update Dependencies

**Backend:**
```bash
cd backend
pip install -r requirements.txt --upgrade
```

**Frontend:**
```bash
cd frontend
npm update
```

## Performance Tips

1. **Use appropriate model size**
   - `llama3.2:1b` - Fast but poor quality
   - `llama3` (8B) - Good balance (recommended)
   - `llama3:70b` - Best quality but slow

2. **Chunk size tuning**
   - Default: 1000 chars with 200 overlap
   - Larger chunks: More context, fewer vectors
   - Smaller chunks: More precise retrieval

3. **Top-K retrieval**
   - Default: 5 chunks
   - Increase for more context
   - Decrease for faster responses

## Example Queries

After uploading research papers:

- "What methodology was used in this study?"
- "List all chemicals mentioned in the experiments"
- "What were the main conclusions?"
- "Show relationships between entities X and Y"

## License

MIT

## Support

For issues, check logs:
- Backend: `docker logs atlas-app`
- PostgreSQL: `docker logs atlas-postgres`
- Qdrant: `docker logs atlas-qdrant`
