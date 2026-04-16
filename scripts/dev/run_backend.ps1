# Run Atlas Backend in Development Mode
$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPath = Join-Path $RepoRoot ".venv"
$BackendDir = Join-Path $RepoRoot "src\backend"

# Optional: port from env (backend reads API_PORT from .env in src/backend)
$Port = 8000
if ($env:API_PORT) { $Port = [int]$env:API_PORT }
$FrameworkHealthUrl = "http://127.0.0.1:$Port/api/framework/health"
$FrameworkToolsUrl = "http://127.0.0.1:$Port/api/framework/tools"

# 1. Check if port is already in use
$InUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($InUse) {
    try {
        $HealthResponse = Invoke-WebRequest -Uri $FrameworkHealthUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($HealthResponse.StatusCode -ge 200 -and $HealthResponse.StatusCode -lt 300) {
            Write-Host ""
            Write-Host "Atlas Framework backend is already running on port $Port." -ForegroundColor Green
            Write-Host "  Health: $FrameworkHealthUrl" -ForegroundColor Gray
            Write-Host "  Tools : $FrameworkToolsUrl" -ForegroundColor Gray
            Write-Host ""
            exit 0
        }
    } catch {
        # Another process is listening on the port but it is not the Atlas Framework backend.
    }

    Write-Host ""
    Write-Host "Port $Port is already in use by a different process." -ForegroundColor Yellow
    Write-Host "  - Stop the other process, or" -ForegroundColor Gray
    Write-Host "  - Use a different port: set API_PORT=8001 in src/backend/.env and run this script again." -ForegroundColor Gray
    Write-Host "  - Expected Atlas Framework health: $FrameworkHealthUrl" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

# 2. Activate Venv
if (Test-Path $VenvPath) {
    Write-Host "Activating venv..." -ForegroundColor Gray
    & (Join-Path $VenvPath "Scripts\Activate.ps1")
} else {
    Write-Warning "No .venv found at $VenvPath"
}

# 3. Set PYTHONPATH to include src/backend so imports work
$env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"

# 4. Run Server
Write-Host "Starting Atlas Framework backend (http://127.0.0.1:$Port)..." -ForegroundColor Cyan
Write-Host "  Health: $FrameworkHealthUrl" -ForegroundColor Gray
Write-Host "  Tools : $FrameworkToolsUrl" -ForegroundColor Gray
Set-Location $BackendDir
python run_server.py
