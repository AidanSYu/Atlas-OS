# Start Both Frontend and Backend
Write-Host "Starting Atlas (Frontend + Backend)..." -ForegroundColor Green

# Start database services
Write-Host "`n[1/3] Starting database services..." -ForegroundColor Yellow
docker-compose up -d db_graph db_vector
Start-Sleep -Seconds 3

# Start backend in background
Write-Host "`n[2/3] Starting backend..." -ForegroundColor Yellow
$backendScript = Join-Path $PSScriptRoot "start-backend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", $backendScript

# Wait a bit for backend to start
Start-Sleep -Seconds 5

# Start frontend
Write-Host "`n[3/3] Starting frontend..." -ForegroundColor Yellow
$frontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", $frontendScript

Write-Host "`n✓ All services starting!" -ForegroundColor Green
Write-Host "`nBackend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "`nNote: Make sure Ollama is running at http://localhost:11434" -ForegroundColor Yellow
