# Atlas 2.0 - Quick Start Guide

## Prerequisites (docker-free)

- Python 3.9+
- PostgreSQL running locally on `localhost:5432` (or set `DB_BACKEND=sqlite`)
- Qdrant running locally on `localhost:6333` (or set `VECTOR_BACKEND=local`)
- Ollama installed locally

## Setup Instructions

### 1. Configure storage

Create `backend/.env` (if missing) and optionally enable fallbacks:

```bash
cd backend
cp .env.example .env  # if you don't have one yet
echo "DB_BACKEND=sqlite" >> .env          # optional fallback
echo "VECTOR_BACKEND=local" >> .env      # optional fallback
```

### 2. Install Ollama Models

Install the required models:

```bash
# Install small 1B parameter model for testing
ollama pull llama3.2:1b

# Install embedding model
ollama pull nomic-embed-text
```

### 3. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Download Spacy Model (Optional, for better entity extraction)

```bash
python -m spacy download en_core_web_sm
```

### 5. Initialize Database

The database will auto-initialize on first run, but you can also manually initialize:

```python
from database import init_db
init_db()
```

### 6. Start Backend Server

```bash
cd backend
python server.py
```

Server starts on `http://localhost:8000`

### 7. Start Frontend (Optional)

```bash
cd frontend
npm install
npm run dev
```

Frontend starts on `http://localhost:3000`

---

## Quick Test

### Upload a Document

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@your_document.pdf"
```

### Query the Knowledge Layer

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?"}'
```

### Check System Health

```bash
curl http://localhost:8000/health
```

---

## Example Queries

### 1. General Question
```json
{
  "query": "What experimental methods are described?"
}
```

### 2. Relationship Query
```
GET /query/relationship?entity1=catalyst&entity2=reaction
```

### 3. Document-Specific Query
```
GET /query/document/{doc_id}?question=What are the main findings?
```

### 4. Search Across Documents
```
GET /query/search?concept=photocatalysis
```

---

## API Endpoints

### Document Management
- `POST /ingest` - Upload and process PDF
- `GET /files` - List all documents
- `GET /files/{doc_id}` - Get specific document
- `DELETE /files/{doc_id}` - Delete document

### Querying
- `POST /chat` - Main query endpoint
- `GET /query/relationship` - Find entity connections
- `GET /query/document/{doc_id}` - Query specific document
- `GET /query/search` - Search across documents

### Knowledge Graph
- `GET /entities` - List entities
- `GET /entities/{entity_id}/relationships` - Get entity relationships
- `GET /graph/types` - Get entity types with counts

### System
- `GET /` - Health check
- `GET /health` - Detailed health status
- `GET /stats` - Knowledge layer statistics

---

## Configuration

Edit `backend/config.py` or create `.env` file:

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=atlas_knowledge
POSTGRES_USER=atlas
POSTGRES_PASSWORD=atlas_secure_password

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K_RETRIEVAL=5
```

---

## Troubleshooting

### PostgreSQL Connection Error
```bash
# Check if PostgreSQL is running
docker ps

# Check connection
docker exec atlas-postgres psql -U atlas -d atlas_knowledge -c "SELECT 1"
```

### Qdrant Not Accessible
```bash
# Check if Qdrant is running
curl http://localhost:6333/healthz

# View logs
docker logs atlas-qdrant
```

### Ollama Model Not Found
```bash
# List installed models
ollama list

# Pull required models
ollama pull llama3.2:1b
ollama pull nomic-embed-text
```

### Database Schema Issues
```python
# Reset database (WARNING: Deletes all data)
from database import reset_db
reset_db()
```

---

## Next Steps

1. Upload sample documents
2. Try different query types
3. Explore the knowledge graph via `/entities`
4. Check system stats with `/stats`
5. Review [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design

---

## Performance Tips

- **First query is slow**: Ollama needs to load models into memory
- **Entity extraction**: Can be slow on large documents; consider processing in background
- **Vector search**: First search after restart may be slower as Qdrant loads data

---

## Data Location

- **Uploaded PDFs**: `backend/data/uploads/`
- **PostgreSQL Data**: `data/postgres/`
- **Qdrant Data**: `data/qdrant/`

---

## Stopping the System

```bash
# Stop Docker services
docker-compose down

# Stop and remove data volumes (WARNING: Deletes all data)
docker-compose down -v
```
