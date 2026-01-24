# Start Backend Services
Write-Host "Starting Atlas Backend..." -ForegroundColor Green

# Check if Docker is running
$dockerRunning = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not running. Please start Docker Desktop or Rancher Desktop." -ForegroundColor Red
    exit 1
}

# Start database services
Write-Host "`nStarting PostgreSQL and Qdrant..." -ForegroundColor Yellow
docker-compose up -d db_graph db_vector

# Wait for services to be healthy
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check if Ollama is running
Write-Host "`nChecking Ollama..." -ForegroundColor Yellow
try {
    $ollamaCheck = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2
    Write-Host "✓ Ollama is running" -ForegroundColor Green
} catch {
    Write-Host "⚠ Warning: Ollama is not running on localhost:11434" -ForegroundColor Yellow
    Write-Host "  Please start Ollama and ensure it is accessible at http://localhost:11434" -ForegroundColor Yellow
}

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

# Navigate to backend directory
Set-Location backend

# Check if virtual environment exists
if (Test-Path "venv") {
    Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1
} else {
    Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    & .\venv\Scripts\Activate.ps1
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Start the backend server
Write-Host "`nStarting FastAPI backend server..." -ForegroundColor Green
Write-Host "Backend will be available at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "API docs at: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop the server`n" -ForegroundColor Yellow

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
