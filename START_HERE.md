# 🎯 START HERE - Complete Setup Instructions

## ⚠️ Important: Make Sure Rancher Desktop is Running!

Before starting, **open Rancher Desktop** and wait for it to fully start. You should see it in your system tray.

---

## 📋 Step-by-Step Instructions

### Step 1: Start Database Services

**Open PowerShell** (as Administrator if needed) in the project folder:

```powershell
cd "c:\Users\aidan\OneDrive - Duke University\Code\ContAInnum_Atlas2.0"
```

**Start PostgreSQL and Qdrant:**

```powershell
docker-compose up -d db_graph db_vector
```

**Wait 10-15 seconds**, then check they're running:

```powershell
docker-compose ps
```

You should see both `atlas-postgres` and `atlas-qdrant` with status "Up".

**If you get Docker errors:**
- Make sure Rancher Desktop is running
- Try restarting Rancher Desktop
- Run PowerShell as Administrator

---

### Step 2: Start Backend Server

**Open a NEW PowerShell window** and run:

```powershell
# Navigate to project
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

**You should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
✓ Database initialized
INFO:     Application startup complete.
```

**✅ Keep this window open!** The backend is now running.

**Test it:** Open http://localhost:8000/health in your browser

---

### Step 3: Start Frontend

**Open ANOTHER NEW PowerShell window** and run:

```powershell
# Navigate to frontend
cd "c:\Users\aidan\OneDrive - Duke University\Code\ContAInnum_Atlas2.0\frontend"

# Start Next.js
npm run dev
```

**You should see:**
```
  ▲ Next.js 14.1.0
  - Local:        http://localhost:3000

  ✓ Ready in 2.5s
```

**✅ Keep this window open too!** The frontend is now running.

---

### Step 4: Open the Application

**Open your browser** and go to:

**http://localhost:3000**

You should see the Atlas interface!

---

## ✅ Verification Checklist

- [ ] Rancher Desktop is running
- [ ] Database containers are running (`docker-compose ps`)
- [ ] Backend is running (http://localhost:8000/health works)
- [ ] Frontend is running (http://localhost:3000 loads)
- [ ] Ollama is running (check with `ollama list`)

---

## 🧪 Test the Application

1. **Upload a PDF:**
   - Use the file sidebar in the web interface
   - Drag and drop a PDF file
   - Wait for "Processing..." to complete

2. **Ask a Question:**
   - Type a question in the chat interface
   - The system will query your knowledge base
   - You should get an answer with citations

3. **View the Graph:**
   - Check the knowledge graph visualization
   - See entities and relationships extracted from documents

---

## 🐛 Troubleshooting

### "Cannot connect to Docker"

**Problem:** Docker/Rancher Desktop not running

**Solution:**
1. Open Rancher Desktop application
2. Wait for it to fully start (check system tray)
3. Try the docker command again

### "Port 8000 already in use"

**Problem:** Another application is using port 8000

**Solution:**
Change the backend port:
```powershell
$env:API_PORT = "8001"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Then update `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### "ModuleNotFoundError: No module named 'app'"

**Problem:** Virtual environment not activated or wrong directory

**Solution:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
# Make sure you see (venv) in your prompt
uvicorn app.main:app --reload
```

### "Cannot connect to PostgreSQL"

**Problem:** Database container not running

**Solution:**
```powershell
docker-compose restart db_graph
# Wait 10 seconds
docker-compose ps
```

### Frontend shows "Failed to fetch"

**Problem:** Backend not running or wrong URL

**Solution:**
1. Check backend is running: http://localhost:8000/health
2. Check `frontend/.env.local` has: `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. Restart frontend

---

## 📝 Quick Reference

**Start databases:**
```powershell
docker-compose up -d db_graph db_vector
```

**Stop databases:**
```powershell
docker-compose down
```

**View logs:**
```powershell
docker-compose logs -f db_graph
docker-compose logs -f db_vector
```

**Backend URL:** http://localhost:8000
**Frontend URL:** http://localhost:3000
**API Docs:** http://localhost:8000/docs

---

## 🎉 You're All Set!

Once everything is running:
- Backend terminal: Shows API requests and processing
- Frontend terminal: Shows Next.js compilation
- Browser: Shows the Atlas interface

**Happy querying!** 🚀
