# Simple Backend Startup Script
Write-Host "Starting Atlas Backend..." -ForegroundColor Green

# Navigate to backend
Set-Location "$PSScriptRoot\backend"

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

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

Write-Host "`nStarting FastAPI server..." -ForegroundColor Green
Write-Host "Backend: http://localhost:8000" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop`n" -ForegroundColor Yellow

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
