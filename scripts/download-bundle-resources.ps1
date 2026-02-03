# Download PostgreSQL and Qdrant binaries into src-tauri/resources for standalone bundle.
# Run from repo root. Creates resources/postgres/bin and resources/qdrant with binaries.
#
# Usage: .\scripts\download-bundle-resources.ps1
#
# If PostgreSQL is very slow (e.g. on campus/VPN): download the zip manually from
#   https://www.enterprisedb.com/download-postgresql-binaries
#   (choose Windows x64, ZIP). Save as:
#   $env:TEMP\postgresql-16.1-1-windows-x64-binaries.zip
# Then re-run this script; it will use the existing file and skip the download.

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path } else { Get-Location }
$ResourcesDir = Join-Path (Join-Path $RepoRoot "src-tauri") "resources"

# Headers so CDNs don't throttle (script-style requests are often slow)
$CommonHeaders = @{
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    "Accept"     = "application/zip, */*"
}

# PostgreSQL (EnterpriseDB Windows x64)
$PgVersion = "16.1-1"
$PgUrl = "https://get.enterprisedb.com/postgresql/postgresql-$PgVersion-windows-x64-binaries.zip"
$PgZip = Join-Path $env:TEMP "postgresql-$PgVersion-windows-x64-binaries.zip"
$PgExtract = Join-Path $env:TEMP "postgresql-$PgVersion-windows-x64"
$PgDest = Join-Path $ResourcesDir "postgres"

# Qdrant
$QdrantVersion = "v1.7.0"
$QdrantUrl = "https://github.com/qdrant/qdrant/releases/download/$QdrantVersion/qdrant-x86_64-pc-windows-msvc.zip"
$QdrantZip = Join-Path $env:TEMP "qdrant-windows.zip"
$QdrantDest = Join-Path $ResourcesDir "qdrant"

function Ensure-Dir { param($Path); New-Item -ItemType Directory -Force -Path $Path | Out-Null }

# --- PostgreSQL ---
if (-not (Test-Path (Join-Path (Join-Path $PgDest "bin") "postgres.exe"))) {
    Ensure-Dir $PgDest
    if (-not (Test-Path $PgZip)) {
        Write-Host "Downloading PostgreSQL $PgVersion (~80 MB). If this is very slow, cancel and use manual download (see script header)."
        try {
            Invoke-WebRequest -Uri $PgUrl -OutFile $PgZip -UseBasicParsing -Headers $CommonHeaders -TimeoutSec 600
        } catch {
            Write-Warning "Download failed or timed out. You can download manually from: https://www.enterprisedb.com/download-postgresql-binaries"
            Write-Warning "Save as: $PgZip"
            throw
        }
    } else {
        Write-Host "Using existing zip: $PgZip"
    }
    Expand-Archive -Path $PgZip -DestinationPath $PgExtract -Force
    $pgBin = Get-ChildItem -Path $PgExtract -Recurse -Filter "postgres.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pgBin) { throw "postgres.exe not found in zip" }
    $PgSrcRoot = $pgBin.Directory.Parent
    Ensure-Dir (Join-Path $PgDest "bin")
    Copy-Item -Path (Join-Path (Join-Path $PgSrcRoot.FullName "bin") "*") -Destination (Join-Path $PgDest "bin") -Recurse -Force
    if (Test-Path (Join-Path $PgSrcRoot.FullName "lib")) {
        Ensure-Dir (Join-Path $PgDest "lib")
        Copy-Item -Path (Join-Path (Join-Path $PgSrcRoot.FullName "lib") "*") -Destination (Join-Path $PgDest "lib") -Recurse -Force
    }
    Remove-Item $PgZip -Force -ErrorAction SilentlyContinue
    Remove-Item $PgExtract -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "PostgreSQL placed in $PgDest"
} else {
    Write-Host "PostgreSQL already present in $PgDest"
}

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
