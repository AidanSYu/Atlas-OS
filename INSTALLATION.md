# 🚀 Atlas Setup & Installation Guide

Complete step-by-step guide to get Atlas running on your machine.

> Note: Docker is no longer required or supported for this project. Use local PostgreSQL + Qdrant services, or enable the SQLite/local vector fallbacks in `backend/.env`.

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Prerequisites Installation](#prerequisites-installation)
3. [Project Setup](#project-setup)
4. [Running Atlas](#running-atlas)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum
- **OS**: Windows 10/11, macOS 12+, or Linux (Ubuntu 20.04+)
- **RAM**: 8 GB
- **Storage**: 10 GB free space
- **CPU**: 4 cores recommended for Ollama

### Recommended
- **RAM**: 16 GB
- **Storage**: 20 GB SSD
- **CPU**: 8+ cores
- **GPU**: Optional, for faster Ollama inference

---

## Prerequisites Installation

### 1. Install PostgreSQL (or use SQLite fallback)

- Preferred: Install PostgreSQL locally and ensure it listens on `localhost:5432`.
- Windows: Use the official installer from https://www.postgresql.org/download/.
- macOS: `brew install postgresql` then `brew services start postgresql`.
- Linux (Ubuntu): `sudo apt-get install postgresql postgresql-contrib` then `sudo systemctl enable --now postgresql`.
- Fallback: set `DB_BACKEND=sqlite` in `backend/.env` to use the bundled SQLite file `data/atlas.db`.

### 2. Install Qdrant (or use local vector fallback)

- Preferred: Install the open-source Qdrant binary and run it on `localhost:6333`.
   - macOS (Homebrew): `brew install qdrant && brew services start qdrant`
   - Linux: Download from https://qdrant.tech/documentation/quick-start/ and run the binary.
   - Windows: Download the release zip from Qdrant GitHub, unzip, and run `qdrant.exe`.
- Fallback: set `VECTOR_BACKEND=local` in `backend/.env` to use the lightweight JSON vector store.

### 3. Install Python 3.10+

**Windows:**
1. Download from: https://www.python.org/downloads/
2. **Important**: Check "Add Python to PATH" during installation
3. Verify:
   ```powershell
   python --version
   ```

**macOS:**
```bash
# Using Homebrew
brew install python@3.11

# Verify
python3 --version
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv python3-pip
```

### 4. Install Node.js 18+

**Windows:**
1. Download LTS from: https://nodejs.org/
2. Run installer with default options
3. Verify:
   ```powershell
   node --version
   npm --version
   ```

**macOS:**
```bash
# Using Homebrew
brew install node

# Verify
node --version
```

**Linux:**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 5. Install Ollama

**Windows:**
1. Download from: https://ollama.ai/download
2. Run the installer
3. Ollama will start automatically as a service
4. Verify in PowerShell:
   ```powershell
   ollama --version
   ```

**macOS:**
```bash
# Using Homebrew
brew install ollama

# Start service
brew services start ollama

# Verify
ollama --version
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh

# Verify
ollama --version
```

### 5. Pull AI Models

This will download ~4.5GB of models:

```bash
# Large language model (4.7GB)
ollama pull llama3

# Embedding model (274MB)
ollama pull nomic-embed-text
```

**Note**: This may take 10-30 minutes depending on your internet speed.

---

## Project Setup

### Option A: Automated Setup (Recommended)

**Windows:**
```powershell
cd "c:\Users\aidan\OneDrive - Duke University\ContAInnum_Atlas2.0"
.\start.ps1
```

**macOS/Linux:**
```bash
cd "/path/to/ContAInnum_Atlas2.0"
chmod +x start.sh
./start.sh
```

The script will:
- ✅ Check all prerequisites
- ✅ Start Neo4j in Docker
- ✅ Set up Python virtual environment
- ✅ Install backend dependencies
- ✅ Set up frontend dependencies
- ✅ Offer to start all services

### Option B: Manual Setup

#### Step 1: Start Neo4j

```bash
cd "c:\Users\aidan\OneDrive - Duke University\ContAInnum_Atlas2.0"
docker-compose up -d
```

Wait 10-15 seconds for Neo4j to fully start.

**Verify**: Open http://localhost:7474
- Username: `neo4j`
- Password: `atlas123456`

#### Step 2: Setup Backend

```powershell
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify .env file exists
# If not, copy from .env.example
```

#### Step 3: Setup Frontend

```bash
# Navigate to frontend (from project root)
cd frontend

# Install dependencies
npm install

# Verify .env.local exists
# Should contain: NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running Atlas

You need **3 terminal windows** running simultaneously:

### Terminal 1: Neo4j (Already running if you used docker-compose)

```bash
# Check status
docker ps

# Should see: atlas-neo4j
```

### Terminal 2: Backend

```powershell
cd backend

# Activate venv
.\venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate   # macOS/Linux

# Start server
python server.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Terminal 3: Frontend

```bash
cd frontend

# Start development server
npm run dev
```

**Expected output:**
```
▲ Next.js 14.1.0
- Local:        http://localhost:3000
- Ready in 2.3s
```

---

## Verification

### 1. Check All Services

| Service | URL | Expected |
|---------|-----|----------|
| Frontend | http://localhost:3000 | Atlas UI loads |
| Backend | http://localhost:8000 | `{"status": "online"}` |
| API Docs | http://localhost:8000/docs | Interactive API docs |
| Neo4j | http://localhost:7474 | Neo4j browser |
| Ollama | Check with `ollama list` | Shows models |

### 2. Test Upload

1. Open http://localhost:3000
2. Find a test PDF file
3. Drag & drop into left sidebar
4. Wait for green checkmark (Status: indexed)

### 3. Test Chat

In the right panel, type:
```
What files do we have?
```

Expected: List of uploaded files

### 4. Test Citation Click

1. Ask: "Summarize page 1 of [your-file].pdf"
2. Click the citation button in the response
3. PDF should open in center panel at page 1

### 5. Test Graph View

1. Click "Graph View" tab in center panel
2. Should see nodes for documents and entities
3. Click a node to view/edit properties

---

## Troubleshooting

### Issue: "Docker not found"

**Windows:**
- Ensure Docker Desktop is running (check system tray)
- Restart Docker Desktop
- Run PowerShell as Administrator

**macOS/Linux:**
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### Issue: "Port already in use"

**Check what's using the port:**
```powershell
# Windows
netstat -ano | findstr :8000

# macOS/Linux
lsof -i :8000
```

**Kill the process:**
```powershell
# Windows (replace PID)
taskkill /PID <PID> /F

# macOS/Linux
kill -9 <PID>
```

### Issue: "Ollama connection failed"

**Check if Ollama is running:**
```bash
# List models
ollama list

# If not running, start it:
# Windows: Search "Ollama" in Start menu and run
# macOS: brew services start ollama
# Linux: systemctl start ollama
```

**Test Ollama:**
```bash
ollama run llama3 "Hello"
```

### Issue: "Module not found" (Python)

```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install --upgrade -r requirements.txt
```

### Issue: "Cannot find module" (Node)

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Issue: Neo4j won't start

```bash
# Stop all containers
docker-compose down

# Remove volumes
docker-compose down -v

# Start fresh
docker-compose up -d

# Check logs
docker logs atlas-neo4j
```

### Issue: Frontend shows CORS errors

1. Ensure backend is running on port 8000
2. Check `.env.local` has correct API URL
3. Restart both backend and frontend

### Issue: Slow responses from chat

**Options:**
1. Use smaller model: Change `OLLAMA_MODEL=mistral` in backend/.env
2. Reduce context: Edit `ingest.py` to use fewer chunks
3. GPU acceleration: Configure Ollama to use GPU
4. Increase RAM: Close other applications

### Issue: PDF won't display

1. Check browser console for errors (F12)
2. Verify file uploaded successfully
3. Try a different PDF
4. Clear browser cache

### Issue: Graph not showing

1. Ensure at least one document is indexed
2. Check Neo4j connection at http://localhost:7474
3. Check browser console for errors
4. Try refreshing the page

---

## Advanced Configuration

### Change Neo4j Password

1. Stop Neo4j: `docker-compose down`
2. Edit `docker-compose.yml`:
   ```yaml
   NEO4J_AUTH=neo4j/your-new-password
   ```
3. Edit `backend/.env`:
   ```
   NEO4J_PASSWORD=your-new-password
   ```
4. Start: `docker-compose up -d`

### Use GPU for Ollama

**Check if GPU is available:**
```bash
ollama run llama3 "test" --verbose
```

Ollama automatically uses GPU if available (NVIDIA/AMD).

### Increase Backend Performance

Edit `backend/config.py`:
```python
# Reduce chunk size for faster processing
chunk_size = 500  # Default: 1000

# Reduce overlap
chunk_overlap = 100  # Default: 200
```

### Production Build

```bash
# Build frontend for production
cd frontend
npm run build
npm start

# Backend (use gunicorn)
cd backend
pip install gunicorn
gunicorn server:app --workers 4 --bind 0.0.0.0:8000
```

---

## Uninstall / Clean Up

### Remove All Data

```bash
# Stop services
docker-compose down

# Remove all data
rm -rf data/uploads/*
rm -rf data/chromadb/*
rm -rf data/neo4j/*
```

### Complete Uninstall

```bash
# Remove Docker containers and volumes
docker-compose down -v

# Remove virtual environment
rm -rf backend/venv

# Remove node modules
rm -rf frontend/node_modules
rm -rf frontend/.next
```

### Uninstall Dependencies

**Docker Desktop**: Uninstall via Control Panel (Windows) or Applications (macOS)

**Ollama**:
```bash
# Windows: Uninstall via Control Panel
# macOS: brew uninstall ollama
# Linux: sudo rm /usr/local/bin/ollama
```

---

## Getting Help

1. **Check logs**:
   - Backend: Look at terminal output
   - Neo4j: `docker logs atlas-neo4j`
   - Browser: Press F12 → Console tab

2. **API Documentation**: http://localhost:8000/docs

3. **Test API directly**:
   ```bash
   curl http://localhost:8000/
   ```

4. **Check project files**:
   - [README.md](README.md) - Overview
   - [QUICKSTART.md](QUICKSTART.md) - Quick reference
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Technical details

---

## Next Steps

Once everything is running:

1. ✅ Upload your first PDF
2. ✅ Chat with the Librarian
3. ✅ Explore the knowledge graph
4. ✅ Edit node properties
5. ✅ Try clicking citations

**Happy researching! 🔬📚**

---

## Version Information

- **Atlas**: v1.0.0 (MVP)
- **Python**: 3.10+
- **Node.js**: 18+
- **Neo4j**: 5.13.0
- **Ollama**: Latest
- **Next.js**: 14.1.0
- **FastAPI**: 0.109.0

Last updated: January 2026
