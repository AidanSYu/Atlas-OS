# Read .env file from config directory
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$EnvPath = Join-Path $RepoRoot "config\.env"
$MetadataPath = Join-Path $RepoRoot "config\aider_model_metadata.json"

if (Test-Path $EnvPath) {
    Get-Content $EnvPath | Where-Object { $_ -notmatch "^#" -and $_ -match "=" } | ForEach-Object {
        $name, $value = $_.split('=', 2)
        $name = $name.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}
else {
    Write-Warning ".env not found at $EnvPath"
}

# Verify keys are loaded
Write-Host "--- Configuration Check ---" -ForegroundColor Gray
if ($env:DEEPSEEK_API_KEY) {
    $masked = $env:DEEPSEEK_API_KEY.Substring(0, [math]::Min(4, $env:DEEPSEEK_API_KEY.Length)) + "..."
    Write-Host "DEEPSEEK_API_KEY: Found ($masked)" -ForegroundColor Green
}
else {
    Write-Host "DEEPSEEK_API_KEY: Missing" -ForegroundColor Red
}

if ($env:MINIMAX_API_KEY) {
    $masked = $env:MINIMAX_API_KEY.Substring(0, [math]::Min(4, $env:MINIMAX_API_KEY.Length)) + "..."
    Write-Host "MINIMAX_API_KEY:  Found ($masked)" -ForegroundColor Green
}
else {
    Write-Host "MINIMAX_API_KEY:  Missing" -ForegroundColor Red
}
Write-Host "---------------------------" -ForegroundColor Gray

# Ensure keys are set
if (-not $env:DEEPSEEK_API_KEY) {
    Write-Host "Error: DEEPSEEK_API_KEY is not set." -ForegroundColor Red
    exit 1
}

if (-not $env:MINIMAX_API_KEY) {
    Write-Host "Error: MINIMAX_API_KEY is not set." -ForegroundColor Red
    Write-Host "Please add MINIMAX_API_KEY to your .env file."
    exit 1
}

# Map keys for Aider
$env:OPENAI_API_KEY = $env:MINIMAX_API_KEY
$env:OPENAI_API_BASE = "https://api.minimax.io/v1"

Write-Host "Launching Aider with DeepSeek R1 (Architect) + MiniMax 2.5 (Editor)..." -ForegroundColor Cyan

# Check if aider is in venv
$aiderPath = "aider"
if (Get-Command "aider" -ErrorAction SilentlyContinue) {
    $aiderPath = "aider"
}
elseif (Test-Path "$RepoRoot\.venv\Scripts\aider.exe") {
    $aiderPath = "$RepoRoot\.venv\Scripts\aider.exe"
}
elseif (Test-Path "$RepoRoot\src\backend\venv\Scripts\aider.exe") {
    $aiderPath = "$RepoRoot\src\backend\venv\Scripts\aider.exe"
}
else {
    Write-Host "Error: 'aider' command not found." -ForegroundColor Red
    Write-Host "Please run: pip install aider-chat" -ForegroundColor Yellow
    exit 1
}

# Run Aider with explicit keys to avoid environment variable flakiness
$deepseekKey = $env:DEEPSEEK_API_KEY
$minimaxKey = $env:MINIMAX_API_KEY

& $aiderPath `
    --architect deepseek/deepseek-reasoner `
    --model openai/MiniMax-M2.5 `
    --editor-model openai/MiniMax-M2.5 `
    --yes-always `
    --api-key deepseek=$deepseekKey `
    --api-key openai=$minimaxKey `
    --model-metadata-file $MetadataPath
