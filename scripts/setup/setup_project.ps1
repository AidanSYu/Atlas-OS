# Nuke-and-Pave + Surgical Install for Atlas 2.0
# Fixes pip infinite backtracking on langgraph/langchain-core by installing
# langgraph first in a clean venv, then the rest of requirements.

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPath = Join-Path $ProjectRoot ".venv"

Write-Host "=== Step 1: Remove existing .venv (if any) ===" -ForegroundColor Cyan
if (Test-Path $VenvPath) {
    Remove-Item -Recurse -Force $VenvPath
    Write-Host "Removed .venv" -ForegroundColor Green
}
else {
    Write-Host "No .venv found, skipping." -ForegroundColor Yellow
}

Write-Host "`n=== Step 2: Create fresh virtual environment ===" -ForegroundColor Cyan
Set-Location $ProjectRoot
python -m venv .venv
if (-not $?) { throw "Failed to create venv" }
Write-Host "Created .venv" -ForegroundColor Green

Write-Host "`n=== Step 3: Surgical install - langgraph first ===" -ForegroundColor Cyan
& (Join-Path $VenvPath "Scripts\Activate.ps1")
pip install langgraph
if (-not $?) { throw "Failed to install langgraph" }
Write-Host "Installed langgraph (and its langchain-core baseline)" -ForegroundColor Green

Write-Host "`n=== Step 4: Install rest of backend requirements ===" -ForegroundColor Cyan
# Configure Aliyun mirror for speed (User Request/Context)
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

Set-Location (Join-Path $ProjectRoot "src\backend")
pip install -r requirements.txt
if (-not $?) { throw "Failed to install requirements.txt" }
Write-Host "Backend dependencies installed." -ForegroundColor Green

Write-Host "`n=== Step 5: Frontend dependencies ===" -ForegroundColor Cyan
Set-Location (Join-Path $ProjectRoot "src\frontend")
npm install
if (-not $?) { throw "Failed to run npm install in frontend" }
Write-Host "Frontend dependencies installed." -ForegroundColor Green

Write-Host "`n=== Step 6: Root / Tauri CLI ===" -ForegroundColor Cyan
Set-Location $ProjectRoot
npm install
if (-not $?) { throw "Failed to run npm install at root" }
Write-Host "Root dependencies (Tauri CLI, etc.) installed." -ForegroundColor Green

Write-Host "`n=== Done. Prereqs ready for deployment. ===" -ForegroundColor Green
Write-Host "Activate backend venv with:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
