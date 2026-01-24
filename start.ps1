# Atlas Quick Start Script (PowerShell)
# This script sets up and starts all Atlas services

Write-Host "🚀 Atlas Quick Start" -ForegroundColor Cyan
Write-Host "====================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "📋 Checking prerequisites..." -ForegroundColor Yellow

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.10+." -ForegroundColor Red
    exit 1
}

# Check Node
try {
    $nodeVersion = node --version
    Write-Host "✅ Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js not found. Please install Node.js 18+." -ForegroundColor Red
    exit 1
}

# Check Ollama
try {
    ollama --version | Out-Null
    Write-Host "✅ Ollama found" -ForegroundColor Green
} catch {
    Write-Host "❌ Ollama not found. Please install Ollama from https://ollama.ai" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🗄️  Checking local services (PostgreSQL :5432, Qdrant :6333)..." -ForegroundColor Yellow
$pgCheck = Test-NetConnection -ComputerName "localhost" -Port 5432 -WarningAction SilentlyContinue
$qdrantCheck = Test-NetConnection -ComputerName "localhost" -Port 6333 -WarningAction SilentlyContinue
if (-not $pgCheck.TcpTestSucceeded) {
    Write-Host "⚠️  PostgreSQL not reachable on localhost:5432. Please start your local Postgres service." -ForegroundColor Yellow
}
if (-not $qdrantCheck.TcpTestSucceeded) {
    Write-Host "⚠️  Qdrant not reachable on localhost:6333. If you prefer, set VECTOR_BACKEND=local in backend/.env to use the local JSON fallback." -ForegroundColor Yellow
}
Write-Host "✅ Service checks complete (proceeding regardless; backend will error if both stores are unreachable)." -ForegroundColor Green

Write-Host ""
Write-Host "🤖 Checking Ollama models..." -ForegroundColor Yellow
$models = ollama list
if ($models -notmatch "llama3") {
    Write-Host "📥 Pulling llama3 model..." -ForegroundColor Cyan
    ollama pull llama3
}
if ($models -notmatch "nomic-embed-text") {
    Write-Host "📥 Pulling nomic-embed-text model..." -ForegroundColor Cyan
    ollama pull nomic-embed-text
}
Write-Host "✅ Ollama models ready" -ForegroundColor Green

Write-Host ""
Write-Host "🐍 Setting up backend..." -ForegroundColor Yellow
Set-Location backend

if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
}

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1

Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -q -r requirements.txt

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file..." -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
}

Write-Host "✅ Backend setup complete" -ForegroundColor Green

Write-Host ""
Write-Host "⚛️  Setting up frontend..." -ForegroundColor Yellow
Set-Location ..\frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    npm install --silent
}

if (-not (Test-Path ".env.local")) {
    Write-Host "Creating .env.local file..." -ForegroundColor Cyan
    "NEXT_PUBLIC_API_URL=http://localhost:8000" | Out-File -FilePath ".env.local" -Encoding utf8
}

Write-Host "✅ Frontend setup complete" -ForegroundColor Green

Set-Location ..

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "✨ Setup complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Service URLs:" -ForegroundColor Yellow
Write-Host "   Frontend:  http://localhost:3000"
Write-Host "   Backend:   http://localhost:8000"
Write-Host "   Postgres:  localhost:5432 (configure in backend/.env)"
Write-Host "   Qdrant:    http://localhost:6333 (or VECTOR_BACKEND=local)"
Write-Host ""
Write-Host "To start the services manually:" -ForegroundColor Yellow
Write-Host "   1. Backend:  cd backend; python server.py"
Write-Host "   2. Frontend: cd frontend; npm run dev"
Write-Host ""

$response = Read-Host "Start services now? (y/n)"
if ($response -eq "y" -or $response -eq "Y") {
    Write-Host ""
    Write-Host "Starting backend..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\venv\Scripts\Activate.ps1; python server.py"
    
    Start-Sleep -Seconds 2
    
    Write-Host "Starting frontend..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
    
    Write-Host ""
    Write-Host "✅ Services started in separate windows!" -ForegroundColor Green
    Write-Host "   Check the new PowerShell windows for logs" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Open http://localhost:3000 in your browser" -ForegroundColor Cyan
} else {
    Write-Host "Services not started. Start them manually when ready." -ForegroundColor Yellow
}
