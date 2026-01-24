# Atlas 2.0 Setup Script
# Run this script to set up the entire system

Write-Host "=" * 60
Write-Host "Atlas 2.0 - Complete System Setup"
Write-Host "=" * 60

# Check Ollama
Write-Host "`nChecking Ollama..."
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "✅ Ollama found"
} else {
    Write-Host "❌ Ollama not found. Please install Ollama from https://ollama.ai"
    exit 1
}

# Check local services
Write-Host "`n🗄️  Checking local services (PostgreSQL :5432, Qdrant :6333)..."
$pgCheck = Test-NetConnection -ComputerName "localhost" -Port 5432 -WarningAction SilentlyContinue
if ($pgCheck.TcpTestSucceeded) {
    Write-Host "✅ PostgreSQL reachable"
} else {
    Write-Host "⚠️  PostgreSQL not reachable on localhost:5432. Start your Postgres service." -ForegroundColor Yellow
}

try {
    $response = Invoke-WebRequest -Uri "http://localhost:6333/healthz" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Qdrant reachable"
    }
} catch {
    Write-Host "⚠️  Qdrant not reachable on localhost:6333. Set VECTOR_BACKEND=local in backend/.env to use the local JSON fallback." -ForegroundColor Yellow
}

# Install Ollama models
Write-Host "`n🤖 Installing Ollama models..."
Write-Host "This may take a few minutes..."

Write-Host "`nPulling llama3.2:1b (small 1B model)..."
ollama pull llama3.2:1b

Write-Host "`nPulling nomic-embed-text (embeddings)..."
ollama pull nomic-embed-text

# Install Python dependencies
Write-Host "`n📚 Installing Python dependencies..."
Set-Location backend
pip install -r requirements.txt

# Initialize database
Write-Host "`n🗄️  Initializing database..."
python init_db.py

Write-Host "`n" + "=" * 60
Write-Host "✅ Setup Complete!"
Write-Host "=" * 60

Write-Host "`nNext steps:"
Write-Host "1. Start the backend server:"
Write-Host "   cd backend"
Write-Host "   python server.py"
Write-Host ""
Write-Host "2. (Optional) Start the frontend:"
Write-Host "   cd frontend"
Write-Host "   npm install"
Write-Host "   npm run dev"
Write-Host ""
Write-Host "3. Access the API:"
Write-Host "   Backend: http://localhost:8000"
Write-Host "   API Docs: http://localhost:8000/docs"
Write-Host "   Frontend: http://localhost:3000 (if started)"
Write-Host ""
Write-Host "4. Try example queries:"
Write-Host "   See EXAMPLE_QUERIES.md for examples"
Write-Host ""
Write-Host "=" * 60
