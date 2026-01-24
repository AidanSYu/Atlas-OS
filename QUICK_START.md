# 🚀 Quick Start Guide

## Everything is Already Set Up! ✅

All dependencies are installed. Just follow these steps:

## Step 1: Start Database Services

**Open PowerShell in the project folder and run:**

```powershell
docker-compose up -d db_graph db_vector
```

Wait 10 seconds, then check they're running:

```powershell
docker-compose ps
```

You should see `atlas-postgres` and `atlas-qdrant` with status "Up".

## Step 2: Start Backend

**Open a NEW PowerShell window** and run:

```powershell
.\start-backend-simple.ps1
```

OR manually:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
$env:POSTGRES_HOST = "localhost"
$env:QDRANT_HOST = "localhost"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Keep this window open!** You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 3: Start Frontend

**Open ANOTHER NEW PowerShell window** and run:

```powershell
.\start-frontend-simple.ps1
```

OR manually:

```powershell
cd frontend
npm run dev
```

**Keep this window open too!** You should see:
```
  ▲ Next.js 14.1.0
  - Local:        http://localhost:3000
```

## Step 4: Open the App

Open your browser and go to: **http://localhost:3000**

## ✅ Verify Everything Works

1. **Backend Health:** http://localhost:8000/health
2. **API Docs:** http://localhost:8000/docs
3. **Frontend:** http://localhost:3000

## 🐛 Common Issues

### "Cannot connect to Docker"
- Make sure **Rancher Desktop** is running
- Check system tray for Rancher Desktop icon

### "Port 8000 already in use"
- Another app is using port 8000
- Change port: `$env:API_PORT = "8001"` and update `frontend/.env.local`

### "Cannot connect to PostgreSQL"
- Restart: `docker-compose restart db_graph`
- Check logs: `docker-compose logs db_graph`

### Backend shows import errors
- Make sure you activated venv: `.\venv\Scripts\Activate.ps1`
- Reinstall: `pip install -r requirements.txt`

## 📋 What You Have Running

- **PostgreSQL** (port 5432) - Knowledge graph database
- **Qdrant** (port 6333) - Vector store
- **Backend API** (port 8000) - FastAPI server
- **Frontend** (port 3000) - Next.js app
- **Ollama** (port 11434) - LLM service (should already be running)

## 🎯 Next Steps

1. Upload a PDF document via the frontend
2. Wait for processing (check backend terminal for progress)
3. Ask questions in the chat interface
4. Explore the knowledge graph visualization

---

**Need help?** Check `SETUP_GUIDE.md` for detailed troubleshooting.
