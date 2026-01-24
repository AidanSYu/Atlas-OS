# Atlas Full System Setup Script
# Run this after installing Docker Desktop, C++ Build Tools, and Ollama

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Atlas Full System Setup" -ForegroundColor White
Write-Host "========================================`n" -ForegroundColor Cyan

# Function to check if a command exists
function Test-Command {
    param($Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Step 1: Check Prerequisites
Write-Host "Step 1: Checking Prerequisites..." -ForegroundColor Yellow

$missingPrereqs = @()

if (-not (Test-Command "docker")) {
    $missingPrereqs += "Docker Desktop"
    Write-Host "  ❌ Docker Desktop not found" -ForegroundColor Red
} else {
    Write-Host "  ✅ Docker Desktop installed" -ForegroundColor Green
}

if (-not (Test-Command "ollama")) {
    $missingPrereqs += "Ollama"
    Write-Host "  ❌ Ollama not found" -ForegroundColor Red
} else {
    Write-Host "  ✅ Ollama installed" -ForegroundColor Green
}

# Check for C++ Build Tools by trying to find cl.exe
$clPath = where.exe cl 2>$null
if (-not $clPath) {
    $missingPrereqs += "Microsoft C++ Build Tools"
    Write-Host "  ⚠️  C++ Build Tools not found" -ForegroundColor Yellow
    Write-Host "     (Required for ChromaDB)" -ForegroundColor Gray
} else {
    Write-Host "  ✅ C++ Build Tools installed" -ForegroundColor Green
}

if ($missingPrereqs.Count -gt 0) {
    Write-Host "`n❌ Missing Prerequisites:" -ForegroundColor Red
    foreach ($prereq in $missingPrereqs) {
        Write-Host "   - $prereq" -ForegroundColor White
    }
    Write-Host "`nPlease install missing components first." -ForegroundColor Yellow
    Write-Host "See SETUP_FULL_SYSTEM.md for installation instructions.`n" -ForegroundColor Cyan
    exit 1
}

Write-Host "`n✅ All prerequisites installed!`n" -ForegroundColor Green

# Step 2: Pull Ollama Models
Write-Host "Step 2: Pulling Ollama Models..." -ForegroundColor Yellow

$models = ollama list 2>&1 | Out-String

if ($models -notmatch "llama3") {
    Write-Host "  📥 Pulling llama3 model (~4.7 GB)..." -ForegroundColor Cyan
    Write-Host "     This may take 10-20 minutes..." -ForegroundColor Gray
    ollama pull llama3
    Write-Host "  ✅ llama3 model downloaded" -ForegroundColor Green
} else {
    Write-Host "  ✅ llama3 model already available" -ForegroundColor Green
}

if ($models -notmatch "nomic-embed-text") {
    Write-Host "  📥 Pulling nomic-embed-text model (~274 MB)..." -ForegroundColor Cyan
    ollama pull nomic-embed-text
    Write-Host "  ✅ nomic-embed-text model downloaded" -ForegroundColor Green
} else {
    Write-Host "  ✅ nomic-embed-text model already available" -ForegroundColor Green
}

# Step 3: Install ChromaDB
Write-Host "`nStep 3: Installing ChromaDB..." -ForegroundColor Yellow

Push-Location backend

# Activate virtual environment
. .\venv\Scripts\Activate.ps1

try {
    python -c "import chromadb; print(chromadb.__version__)" 2>$null | Out-Null
    Write-Host "  ✅ ChromaDB already installed" -ForegroundColor Green
}
catch {
    Write-Host "  📦 Installing ChromaDB..." -ForegroundColor Cyan
    pip install chromadb==0.4.22
    Write-Host "  ✅ ChromaDB installed" -ForegroundColor Green
}

Pop-Location

# Step 4: Start Neo4j
Write-Host "`nStep 4: Starting Neo4j..." -ForegroundColor Yellow

# Check if Docker daemon is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "  ❌ Docker daemon is not running" -ForegroundColor Red
    Write-Host "     Please start Docker Desktop and try again.`n" -ForegroundColor Yellow
    exit 1
}

# Check if Neo4j is already running
$neo4jRunning = docker ps --filter "name=atlas-neo4j" --format "{{.Names}}" 2>$null

if ($neo4jRunning -eq "atlas-neo4j") {
    Write-Host "  ✅ Neo4j already running" -ForegroundColor Green
} else {
    Write-Host "  🚀 Starting Neo4j container..." -ForegroundColor Cyan
    docker-compose up -d
    Write-Host "  ⏳ Waiting for Neo4j to be ready..." -ForegroundColor Gray
    Start-Sleep -Seconds 10
    Write-Host "  ✅ Neo4j started" -ForegroundColor Green
}

# Step 5: Verify Neo4j Connection
Write-Host "`nStep 5: Verifying Neo4j Connection..." -ForegroundColor Yellow

$maxRetries = 5
$retryCount = 0
$connected = $false

while ($retryCount -lt $maxRetries -and -not $connected) {
    try {
        Push-Location backend
        . .\venv\Scripts\Activate.ps1
        $result = python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password123')); driver.verify_connectivity(); print('OK')" 2>&1
        Pop-Location
        
        if ($result -match "OK") {
            $connected = $true
            Write-Host "  ✅ Neo4j connection successful" -ForegroundColor Green
        } else {
            throw "Connection failed"
        }
    }
    catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "  ⏳ Waiting for Neo4j... (attempt $retryCount/$maxRetries)" -ForegroundColor Gray
            Start-Sleep -Seconds 5
        }
    }
}

if (-not $connected) {
    Write-Host "  ⚠️  Could not verify Neo4j connection" -ForegroundColor Yellow
    Write-Host "     The system may still work. Check http://localhost:7474" -ForegroundColor Gray
}

# Step 6: Create startup scripts
Write-Host "`nStep 6: Creating Startup Scripts..." -ForegroundColor Yellow

# Create start-full-backend.ps1
$backendScript = @'
# Start Full Atlas Backend
$ErrorActionPreference = "Stop"

Write-Host "`n🚀 Starting Atlas Backend (Full Mode)..." -ForegroundColor Cyan

cd backend
.\venv\Scripts\Activate.ps1
python server.py
'@

Set-Content -Path "start-full-backend.ps1" -Value $backendScript
Write-Host "  ✅ Created start-full-backend.ps1" -ForegroundColor Green

# Create start-frontend.ps1 if it doesn't exist
if (-not (Test-Path "start-frontend.ps1")) {
    $frontendScript = @'
# Start Atlas Frontend
$ErrorActionPreference = "Stop"

Write-Host "`n🎨 Starting Atlas Frontend..." -ForegroundColor Cyan

cd frontend
npm run dev
'@
    Set-Content -Path "start-frontend.ps1" -Value $frontendScript
    Write-Host "  ✅ Created start-frontend.ps1" -ForegroundColor Green
}

# Create start-all.ps1
$startAllScript = @'
# Start Full Atlas System
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Starting Full Atlas System" -ForegroundColor White
Write-Host "========================================`n" -ForegroundColor Cyan

# Check Docker
try {
    docker ps | Out-Null
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first.`n" -ForegroundColor Red
    exit 1
}

# Start Neo4j
Write-Host "🗄️  Starting Neo4j..." -ForegroundColor Yellow
docker-compose up -d
Start-Sleep -Seconds 5

# Start Backend in new window
Write-Host "🚀 Starting Backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-File", "start-full-backend.ps1"

Start-Sleep -Seconds 3

# Start Frontend in new window
Write-Host "🎨 Starting Frontend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-File", "start-frontend.ps1"

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "   Atlas System Starting!" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
Write-Host "`n📍 Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "📍 Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "📍 Neo4j:    http://localhost:7474" -ForegroundColor Cyan
Write-Host "`n⏳ Wait 10-15 seconds for all services to be ready..." -ForegroundColor Yellow
Write-Host "`nPress any key to exit this window (services will keep running)...`n" -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
'@

Set-Content -Path "start-all.ps1" -Value $startAllScript
Write-Host "  ✅ Created start-all.ps1" -ForegroundColor Green

# Final Summary
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "   Setup Complete! 🎉" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green

Write-Host "`n📋 Quick Start Commands:" -ForegroundColor Cyan
Write-Host "`n1. Start everything:" -ForegroundColor Yellow
Write-Host "   .\start-all.ps1" -ForegroundColor White

Write-Host "`n2. Or start manually:" -ForegroundColor Yellow
Write-Host "   docker-compose up -d" -ForegroundColor Gray
Write-Host "   .\start-full-backend.ps1" -ForegroundColor Gray
Write-Host "   .\start-frontend.ps1" -ForegroundColor Gray

Write-Host "`n3. Access the application:" -ForegroundColor Yellow
Write-Host "   http://localhost:3000" -ForegroundColor White

Write-Host "`n📊 System URLs:" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   Neo4j:    http://localhost:7474" -ForegroundColor White
Write-Host "             (user: neo4j, pass: password123)" -ForegroundColor Gray

Write-Host "`n📚 Documentation:" -ForegroundColor Cyan
Write-Host "   SETUP_FULL_SYSTEM.md - Complete setup guide" -ForegroundColor White
Write-Host "   README.md - Main documentation" -ForegroundColor White
Write-Host "   QUICKSTART.md - Quick reference" -ForegroundColor White

Write-Host "`n✨ What's New with Full System:" -ForegroundColor Cyan
Write-Host "   ✅ AI-powered entity extraction" -ForegroundColor Green
Write-Host "   ✅ Hybrid RAG search (Vector + Graph)" -ForegroundColor Green
Write-Host "   ✅ Intelligent citations with context" -ForegroundColor Green
Write-Host "   ✅ Knowledge graph visualization" -ForegroundColor Green
Write-Host "   ✅ Real-time document analysis" -ForegroundColor Green

Write-Host "`nReady to use! Run: .\start-all.ps1`n" -ForegroundColor Yellow
