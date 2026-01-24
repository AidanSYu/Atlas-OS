# How to Run Atlas (Frontend + Backend)

## Prerequisites

1. **Ollama** must be running locally on your machine
   - Download from: https://ollama.ai
   - Start Ollama service
   - Pull the required model: `ollama pull llama3.2:1b`
   - Pull the embedding model: `ollama pull nomic-embed-text`

2. **Docker** or **Docker Compose** (for PostgreSQL and Qdrant)

3. **Node.js** (v18+) and **npm** (for frontend)

## Quick Start

### Option 1: Run Everything with Docker Compose (Backend Only)

The backend services (PostgreSQL, Qdrant, FastAPI) can run in Docker, but Ollama must run on the host.

```bash
# Start database services and backend API
docker-compose up -d

# Check logs
docker-compose logs -f app

# Backend API will be at http://localhost:8000
```

### Option 2: Run Backend Locally, Frontend Locally (Recommended for Development)

#### Step 1: Start Database Services

```bash
# Start only PostgreSQL and Qdrant
docker-compose up -d db_graph db_vector

# Verify they're running
docker-compose ps
```

#### Step 2: Start Backend API

```bash
cd backend

# Install Python dependencies (if not already done)
pip install -r requirements.txt

# Set environment variables (or create .env file)
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=atlas_knowledge
export POSTGRES_USER=atlas
export POSTGRES_PASSWORD=atlas_secure_password
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export OLLAMA_BASE_URL=http://localhost:11434

# Run the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`

#### Step 3: Start Frontend

Open a **new terminal**:

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start Next.js dev server
npm run dev
```

Frontend will be available at: `http://localhost:3000`

## Verify Everything is Working

### 1. Check Backend Health

```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "services": {...}
}
```

### 2. Check Frontend

Open browser to `http://localhost:3000`

You should see the Atlas interface.

### 3. Test Document Upload

1. Go to `http://localhost:3000`
2. Upload a PDF file using the file sidebar
3. Wait for processing to complete

### 4. Test Chat

1. Type a question in the chat interface
2. The system should query the knowledge base and return an answer

## Troubleshooting

### Backend won't start

**Error: "Cannot connect to PostgreSQL"**
- Make sure `db_graph` container is running: `docker-compose ps`
- Check PostgreSQL logs: `docker-compose logs db_graph`
- Verify connection string in environment variables

**Error: "Cannot connect to Qdrant"**
- Make sure `db_vector` container is running: `docker-compose ps`
- Check Qdrant logs: `docker-compose logs db_vector`
- Verify Qdrant is accessible at `http://localhost:6333`

**Error: "Cannot connect to Ollama"**
- Make sure Ollama is running: `ollama list`
- Check Ollama is accessible: `curl http://localhost:11434/api/tags`
- On Windows, you may need to use `http://host.docker.internal:11434` if running backend in Docker

### Frontend won't connect to backend

**Error: "Failed to fetch" or CORS errors**
- Make sure backend is running on port 8000
- Check browser console for errors
- Verify `NEXT_PUBLIC_API_URL` environment variable (defaults to `http://localhost:8000`)

### Database migration issues

If you need to reset the database:

```bash
# Stop containers
docker-compose down

# Remove database volume
docker volume rm atlas-postgres-data  # or delete ./data/postgres

# Restart
docker-compose up -d db_graph
```

## Environment Variables

### Backend (.env file in `backend/`)

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=atlas_knowledge
POSTGRES_USER=atlas
POSTGRES_PASSWORD=atlas_secure_password
QDRANT_HOST=localhost
QDRANT_PORT=6333
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
UPLOAD_DIR=./data/uploads
API_HOST=0.0.0.0
API_PORT=8000
```

### Frontend (.env.local file in `frontend/`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Production Deployment

For production, you'll want to:

1. Build the frontend: `cd frontend && npm run build && npm start`
2. Use a production WSGI server for backend (e.g., Gunicorn)
3. Set up proper environment variables
4. Use a reverse proxy (nginx) for routing
5. Configure SSL/TLS certificates

## Ports Used

- **3000**: Frontend (Next.js)
- **8000**: Backend API (FastAPI)
- **5432**: PostgreSQL
- **6333**: Qdrant HTTP API
- **6334**: Qdrant gRPC
- **11434**: Ollama (must run on host, not in Docker)
