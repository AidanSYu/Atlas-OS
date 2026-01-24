# 🚀 Full System Setup Guide

This guide will help you install all dependencies for the complete Atlas system with AI features.

---

## 📋 Prerequisites Checklist

Before starting, you'll need to install:

1. ✅ **Python 3.10+** - Already installed
2. ✅ **Node.js** - Already installed
3. ⚠️ **Docker Desktop** - Not installed
4. ⚠️ **Microsoft C++ Build Tools** - Not installed
5. ⚠️ **Ollama** - Not installed

---

## Step 1: Install Docker Desktop

### Download and Install

1. **Download Docker Desktop for Windows**:
   - Visit: https://www.docker.com/products/docker-desktop
   - Click "Download for Windows"
   - File size: ~500 MB

2. **Run the Installer**:
   - Double-click `Docker Desktop Installer.exe`
   - Follow the installation wizard
   - **Important**: Enable WSL 2 when prompted (recommended)

3. **Restart Your Computer**:
   - Docker requires a restart to complete installation

4. **Verify Installation**:
   ```powershell
   docker --version
   docker-compose --version
   ```

### Expected Output:
```
Docker version 24.x.x
Docker Compose version v2.x.x
```

---

## Step 2: Install Microsoft C++ Build Tools

ChromaDB requires C++ build tools to compile native extensions.

### Download and Install

1. **Download Visual Studio Build Tools**:
   - Visit: https://visualstudio.microsoft.com/visual-cpp-build-tools/
   - Click "Download Build Tools"
   - File size: ~1.5 GB

2. **Run the Installer**:
   - Double-click the downloaded file
   - Select "Desktop development with C++"
   - Click "Install"
   - This may take 10-20 minutes

3. **Restart Your Terminal**:
   - Close all PowerShell windows
   - Open a new PowerShell window

4. **Verify Installation**:
   ```powershell
   cl
   ```
   Should show Microsoft C/C++ Compiler information

---

## Step 3: Install Ollama

Ollama provides local AI inference.

### Download and Install

1. **Download Ollama for Windows**:
   - Visit: https://ollama.ai/download
   - Click "Download for Windows"
   - File size: ~300 MB

2. **Run the Installer**:
   - Double-click `OllamaSetup.exe`
   - Follow the installation wizard

3. **Verify Installation**:
   ```powershell
   ollama --version
   ```

4. **Pull Required Models**:
   ```powershell
   ollama pull llama3
   ollama pull nomic-embed-text
   ```
   - `llama3`: ~4.7 GB (text generation)
   - `nomic-embed-text`: ~274 MB (embeddings)
   - This will take 10-30 minutes depending on your internet speed

5. **Verify Models**:
   ```powershell
   ollama list
   ```
   Should show both models

---

## Step 4: Install ChromaDB

Now that C++ Build Tools are installed, we can install ChromaDB.

### Install in Backend Virtual Environment

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install chromadb==0.4.22
```

### Verify Installation:
```powershell
python -c "import chromadb; print(chromadb.__version__)"
```

Should output: `0.4.22`

---

## Step 5: Start Neo4j with Docker

### Start Neo4j Container

```powershell
# Navigate to project root
cd "C:\Users\aidan\OneDrive - Duke University\ContAInnum_Atlas2.0"

# Start Neo4j
docker-compose up -d
```

### Verify Neo4j is Running:

```powershell
docker ps
```

Should show a container with `neo4j:5.13.0`

### Access Neo4j Browser:
- Open: http://localhost:7474
- Username: `neo4j`
- Password: `password123` (default from docker-compose.yml)

---

## Step 6: Start the Full Backend

### Stop Demo Backend (if running)

```powershell
Get-Process python | Where-Object {$_.Path -like "*Atlas2.0*"} | Stop-Process -Force
```

### Start Full Backend

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python server.py
```

### Expected Output:
```
🚀 Starting Atlas Backend
📊 ChromaDB: Connected
🗄️  Neo4j: Connected
🤖 Ollama: Available
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 7: Verify Full System

### Test Backend API

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/"
```

Should return:
```json
{
  "status": "online",
  "service": "Atlas API",
  "version": "1.0.0",
  "features": {
    "vectordb": true,
    "graphdb": true,
    "llm": true
  }
}
```

### Access Frontend

Open in browser: http://localhost:3000

---

## 🎉 Full Features Now Available

With all dependencies installed, you now have:

### ✅ Document Processing
- PDF text extraction
- Automatic chunking (1000 chars)
- Vector embeddings with Ollama
- Storage in ChromaDB

### ✅ AI-Powered Entity Extraction
- LLM analyzes document content
- Extracts entities (chemicals, reactions, measurements)
- Creates knowledge graph in Neo4j
- Automatic relationship detection

### ✅ Hybrid RAG Search
- Vector similarity search (ChromaDB)
- Graph traversal queries (Neo4j)
- Combined context for LLM responses
- Intelligent answer generation

### ✅ Smart Citations
- Source tracking with page numbers
- Clickable citations in chat
- Jump to exact PDF location
- Confidence scoring

### ✅ Graph Editing
- Visual graph exploration
- Manual node editing
- Relationship management
- Real-time updates

---

## 📊 System Resource Usage

With full system running:

| Component | RAM | Storage | Notes |
|-----------|-----|---------|-------|
| Neo4j | ~512 MB | ~100 MB | Graph database |
| Ollama | ~4-6 GB | ~5 GB | LLM inference |
| ChromaDB | ~500 MB | Variable | Vector store |
| Backend | ~200 MB | - | Python/FastAPI |
| Frontend | ~100 MB | - | Node.js/Next.js |
| **Total** | **~6-8 GB** | **~5 GB** | While running |

---

## 🔧 Troubleshooting

### Docker Issues

**Problem**: "Docker daemon is not running"
```powershell
# Open Docker Desktop application
# Wait for it to start (green icon in system tray)
```

**Problem**: "Cannot connect to Docker daemon"
```powershell
# Restart Docker Desktop
# Or restart your computer
```

### Neo4j Issues

**Problem**: "Connection refused to localhost:7687"
```powershell
# Check if container is running
docker ps

# View container logs
docker logs atlas-neo4j

# Restart container
docker-compose restart
```

### ChromaDB Issues

**Problem**: "Microsoft Visual C++ 14.0 or greater is required"
```powershell
# Install C++ Build Tools (see Step 2)
# Then reinstall ChromaDB
pip uninstall chromadb
pip install chromadb==0.4.22
```

### Ollama Issues

**Problem**: "Connection refused to localhost:11434"
```powershell
# Check if Ollama is running
Get-Process ollama

# Restart Ollama service
# Or run: ollama serve
```

**Problem**: "Model not found"
```powershell
# Re-pull the model
ollama pull llama3
```

---

## 🚨 Quick Commands Reference

### Start Everything
```powershell
# 1. Start Docker Desktop (open application)

# 2. Start Neo4j
docker-compose up -d

# 3. Start Backend (in terminal 1)
cd backend
.\venv\Scripts\Activate.ps1
python server.py

# 4. Start Frontend (in terminal 2)
cd frontend
npm run dev
```

### Stop Everything
```powershell
# Stop Backend: Ctrl+C in backend terminal
# Stop Frontend: Ctrl+C in frontend terminal

# Stop Neo4j
docker-compose down

# Stop Docker Desktop: Close application
```

### Check Status
```powershell
# Check Docker
docker ps

# Check Backend
Invoke-RestMethod -Uri "http://localhost:8000/"

# Check Frontend
Test-NetConnection -ComputerName localhost -Port 3000

# Check Ollama
ollama list
```

---

## 🎯 Next Steps After Installation

1. **Upload a Test Document**:
   - Drag a PDF into the left sidebar
   - Wait for "Indexed ✅" status
   - This will take longer on first upload (30-60 seconds)

2. **Test AI Chat**:
   - Ask: "What chemicals are mentioned in the document?"
   - Click on citations to jump to PDF pages
   - Try: "What reactions are described?"

3. **Explore the Graph**:
   - Switch to "Graph View" tab
   - See extracted entities as nodes
   - Click nodes to edit properties
   - Watch relationships between entities

4. **Compare with Demo Mode**:
   - Demo mode: Basic file list, simple responses
   - Full mode: Intelligent analysis, entity extraction, cited answers

---

## 📚 Additional Resources

- **Docker Documentation**: https://docs.docker.com/
- **Neo4j Documentation**: https://neo4j.com/docs/
- **Ollama Documentation**: https://github.com/ollama/ollama
- **ChromaDB Documentation**: https://docs.trychroma.com/

---

## ⚠️ Important Notes

1. **First Upload is Slow**: Initial document processing takes longer (30-60s) as models warm up
2. **Internet Required**: Only for initial downloads (Docker images, Ollama models)
3. **Disk Space**: Ensure you have at least 10 GB free space
4. **RAM**: 8 GB minimum recommended, 16 GB ideal
5. **Windows Version**: Windows 10/11 with WSL 2 support

---

Built with ❤️ for scientific research

For issues, check the troubleshooting section or the main [README.md](README.md)
