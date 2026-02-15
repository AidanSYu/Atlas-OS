# Force Reinstall Torch and Llama-cpp with CUDA
$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPath = Join-Path $RepoRoot ".venv"

# 1. Activate Venv
if (Test-Path $VenvPath) {
    Write-Host "Activating venv..." -ForegroundColor Gray
    & (Join-Path $VenvPath "Scripts\Activate.ps1")
} else {
    Write-Error "No .venv found at $VenvPath"
}

# 2. Uninstall existing
Write-Host "Uninstalling CPU versions..." -ForegroundColor Yellow
pip uninstall -y torch torchvision torchaudio llama-cpp-python

# 3. Install PyTorch with CUDA 12.4 (Stable for Windows)
Write-Host "Installing PyTorch (CUDA 12.4)..." -ForegroundColor Cyan
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 4. Install llama-cpp-python with CUDA
Write-Host "Installing llama-cpp-python (CUDA)..." -ForegroundColor Cyan
# Set environment variables for the build
$env:CMAKE_ARGS = "-DGGML_CUDA=on"
$env:FORCE_CMAKE = "1"
pip install llama-cpp-python --no-cache-dir --force-reinstall --upgrade

Write-Host "GPU Setup Complete. Run scripts/dev/check_gpu.py to verify." -ForegroundColor Green
