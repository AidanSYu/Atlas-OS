# Install pre-built llama-cpp-python wheel with CUDA 12.4 support
$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPath = Join-Path $RepoRoot ".venv"

# 1. Activate Venv
if (Test-Path $VenvPath) {
    Write-Host "Activating venv..." -ForegroundColor Gray
    & (Join-Path $VenvPath "Scripts\Activate.ps1")
}

# 2. Uninstall broken version
Write-Host "Uninstalling broken llama-cpp-python..."
pip uninstall -y llama-cpp-python

# 3. Install pre-built wheel for CUDA 12.4
# Using abetlen's official wheel repo
Write-Host "Installing pre-built wheel from https://abetlen.github.io/llama-cpp-python/whl/cu124 ..." -ForegroundColor Cyan
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --force-reinstall --no-cache-dir

Write-Host "Done. Verify with scripts/dev/check_gpu.py" -ForegroundColor Green
