# Download PostgreSQL and Qdrant binaries into src-tauri/resources for standalone bundle.
# Run from repo root. Creates resources/postgres/bin and resources/qdrant with binaries.
#
# Usage: .\scripts\download-bundle-resources.ps1
#
# Usage: .\scripts\download-bundle-resources.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path } else { Get-Location }
$ResourcesDir = Join-Path (Join-Path $RepoRoot "src-tauri") "resources"

# Headers so CDNs don't throttle (script-style requests are often slow)
$CommonHeaders = @{
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    "Accept"     = "application/zip, */*"
}


# Qdrant
$QdrantVersion = "v1.7.0"
$QdrantUrl = "https://github.com/qdrant/qdrant/releases/download/$QdrantVersion/qdrant-x86_64-pc-windows-msvc.zip"
$QdrantZip = Join-Path $env:TEMP "qdrant-windows.zip"
$QdrantDest = Join-Path $ResourcesDir "qdrant"

function Ensure-Dir { param($Path); New-Item -ItemType Directory -Force -Path $Path | Out-Null }



# --- Qdrant ---
if (-not (Test-Path (Join-Path $QdrantDest "qdrant.exe"))) {
    Write-Host "Downloading Qdrant $QdrantVersion..."
    Ensure-Dir $QdrantDest
    Invoke-WebRequest -Uri $QdrantUrl -OutFile $QdrantZip -UseBasicParsing -Headers $CommonHeaders -TimeoutSec 300
    Expand-Archive -Path $QdrantZip -DestinationPath $QdrantDest -Force
    $qdrantExe = Get-ChildItem -Path $QdrantDest -Filter "qdrant*.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($qdrantExe -and $qdrantExe.DirectoryName -ne $QdrantDest) {
        Move-Item -Path $qdrantExe.FullName -Destination (Join-Path $QdrantDest "qdrant.exe") -Force
    }
    Remove-Item $QdrantZip -Force -ErrorAction SilentlyContinue
    Write-Host "Qdrant placed in $QdrantDest"
} else {
    Write-Host "Qdrant already present in $QdrantDest"
}

Write-Host "Done. Resources are in $ResourcesDir"
Write-Host "Build backend: .\build-backend.ps1"
Write-Host "Build full app: npm run tauri:build"
