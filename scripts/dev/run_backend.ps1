# Run Atlas Backend in Development Mode
$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPath = Join-Path $RepoRoot ".venv"

# 1. Activate Venv
if (Test-Path $VenvPath) {
    Write-Host "Activating venv..." -ForegroundColor Gray
    & (Join-Path $VenvPath "Scripts\Activate.ps1")
} else {
    Write-Warning "No .venv found at $VenvPath"
}

# 2. Set PYTHONPATH to include src/backend so imports work
$BackendDir = Join-Path $RepoRoot "src\backend"
$env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"

# 3. Run Server
Write-Host "Starting Backend Server..." -ForegroundColor Cyan
Set-Location $BackendDir
python run_server.py
