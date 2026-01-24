# Quick Setup Guide - Step by Step

## ✅ Prerequisites Check

You already have:
- ✅ Python 3.12.10
- ✅ Node.js v24.11.1
- ✅ Docker (Rancher Desktop)
- ✅ Ollama 0.14.3
- ✅ Required Ollama models (llama3.2:1b, nomic-embed-text)
- ✅ Backend Python dependencies installed
- ✅ Frontend Node.js dependencies installed

## 🚀 Starting the Application

### Step 1: Make sure Rancher Desktop is running

1. Open Rancher Desktop application
2. Wait for it to fully start (check the system tray icon)

### Step 2: Start Database Services

Open PowerShell in the project root and run:

```powershell
cd "c:\Users\aidan\OneDrive - Duke University\Code\ContAInnum_Atlas2.0"
docker-compose up -d db_graph db_vector
```

Wait about 10 seconds for services to start, then verify:

```powershell
docker-compose ps
```

You should see `atlas-postgres` and `atlas-qdrant` running.

### Step 3: Start Backend

Open a **new PowerShell window** and run:

```powershell
cd "c:\Users\aidan\OneDrive - Duke University\Code\ContAInnum_Atlas2.0\backend"

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Set environment variables
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "atlas_knowledge"
$env:POSTGRES_USER = "atlas"
$env:POSTGRES_PASSWORD = "atlas_secure_password"
$env:QDRANT_HOST = "localhost"
$env:QDRANT_PORT = "6333"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2:1b"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
$env:UPLOAD_DIR = "./data/uploads"
$env:API_HOST = "0.0.0.0"
$env:API_PORT = "8000"

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Keep this window open!**

### Step 4: Start Frontend

Open **another new PowerShell window** and run:

```powershell
cd "c:\Users\aidan\OneDrive - Duke University\Code\ContAInnum_Atlas2.0\frontend"
npm run dev
```

You should see:
```
  ▲ Next.js 14.1.0
  - Local:        http://localhost:3000
```

**Keep this window open too!**

### Step 5: Open the Application

Open your browser and go to: **http://localhost:3000**

## 🧪 Testing

1. **Check Backend Health:**
   - Open: http://localhost:8000/health
   - Should show: `{"status": "healthy", ...}`

2. **Check API Docs:**
   - Open: http://localhost:8000/docs
   - Should show FastAPI interactive documentation

3. **Upload a PDF:**
   - Go to http://localhost:3000
   - Use the file sidebar to upload a PDF
   - Wait for processing to complete

4. **Test Chat:**
   - Type a question in the chat interface
   - The system should query your knowledge base

## 🐛 Troubleshooting

### "Cannot connect to Docker"

**Solution:** Make sure Rancher Desktop is running. Check the system tray.

### "Cannot connect to PostgreSQL"

**Solution:** 
```powershell
docker-compose restart db_graph
# Wait 10 seconds
docker-compose ps
```

### "Cannot connect to Qdrant"

**Solution:**
```powershell
docker-compose restart db_vector
# Wait 10 seconds
docker-compose ps
```

### "ModuleNotFoundError" in backend

**Solution:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Frontend shows "Failed to fetch"

**Solution:**
1. Make sure backend is running (check http://localhost:8000/health)
2. Check `frontend/.env.local` has: `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. Restart frontend: `npm run dev`

### Port already in use

**Solution:**
- Backend (8000): Change `$env:API_PORT = "8001"` and update frontend `.env.local`
- Frontend (3000): Next.js will automatically use 3001

## 📝 Quick Commands Reference

**Start databases:**
```powershell
docker-compose up -d db_graph db_vector
```

**Stop databases:**
```powershell
docker-compose down
```

**View database logs:**
```powershell
docker-compose logs -f db_graph
docker-compose logs -f db_vector
```

**Reset database (WARNING: deletes all data):**
```powershell
docker-compose down
Remove-Item -Recurse -Force .\data\postgres
docker-compose up -d db_graph
```

## 🎯 Next Steps

Once everything is running:
1. Upload some PDF documents
2. Ask questions in the chat
3. Explore the knowledge graph visualization
4. Check the API documentation at http://localhost:8000/docs
