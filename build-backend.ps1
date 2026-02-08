# Build Atlas backend with PyInstaller (onedir) and copy to src-tauri/resources/atlas-backend.
# Run from repo root. Requires: Python with PyInstaller, backend dependencies installed.
# Onedir enables fast incremental builds (only changed files replaced).
#
# Usage: .\build-backend.ps1 [-Force] [-IncludeModels] [-SkipIfUnchanged]
# Then: npx tauri build

param(
    [switch]$Force,
    [switch]$IncludeModels,
    [switch]$SkipIfUnchanged
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$ResourcesDir = Join-Path (Join-Path $RepoRoot "src-tauri") "resources"
$BackendResourceDir = Join-Path $ResourcesDir "atlas-backend"

# Onedir output: dist/atlas-backend/ containing atlas-backend.exe (Windows) or atlas-backend (Unix)
$ExeNames = @{
    "win32"   = "atlas-backend.exe"
    "darwin"  = "atlas-backend"
    "linux"   = "atlas-backend"
}

# Detect platform
if ($env:OS -eq "Windows_NT") { $Platform = "win32" }
elseif ($IsMacOS) { $Platform = "darwin" }
else { $Platform = "linux" }

$DistDir = Join-Path (Join-Path $BackendDir "dist") "atlas-backend"
$DistExe = Join-Path $DistDir $ExeNames[$Platform]

function Get-LatestWriteTime {
    param([string[]]$Paths)
    $latest = $null
    foreach ($path in $Paths) {
        if (Test-Path $path) {
            $items = Get-ChildItem -Path $path -Recurse -File -ErrorAction SilentlyContinue
            foreach ($item in $items) {
                if (-not $latest -or $item.LastWriteTime -gt $latest) {
                    $latest = $item.LastWriteTime
                }
            }
        }
    }
    return $latest
}

if ($SkipIfUnchanged -and -not $Force -and (Test-Path $DistExe)) {
    $sourceLatest = Get-LatestWriteTime @(
        (Join-Path $BackendDir "app"),
        (Join-Path $BackendDir "run_server.py"),
        (Join-Path $BackendDir "atlas.spec"),
        (Join-Path $BackendDir "requirements.txt")
    )
    $distLatest = Get-LatestWriteTime @($DistDir)
    if ($sourceLatest -and $distLatest -and $sourceLatest -le $distLatest) {
        Write-Host "Skipping PyInstaller (backend unchanged)."
        New-Item -ItemType Directory -Force -Path $ResourcesDir | Out-Null
        if (Test-Path $BackendResourceDir) { Remove-Item -Recurse -Force $BackendResourceDir }
        Copy-Item -Recurse -Force $DistDir $BackendResourceDir
        Write-Host "Copied to $BackendResourceDir"
        Write-Host "Done. Run: npx tauri build"
        Write-Host ""
        return
    }
}

Write-Host "Building Atlas backend (PyInstaller onedir) for $Platform..."

Push-Location $BackendDir
try {
    if ($IncludeModels) {
        $env:ATLAS_INCLUDE_MODELS = "1"
    } else {
        $env:ATLAS_INCLUDE_MODELS = "0"
    }
    $PyInstallerArgs = @("--noconfirm", "atlas.spec")
    $PyInstallerCmd = "pyinstaller"
    if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
        $VenvPython = Join-Path (Join-Path (Join-Path $RepoRoot ".venv") "Scripts") "python.exe"
        if (Test-Path $VenvPython) {
            $PyInstallerCmd = $VenvPython
        } else {
            Write-Error "PyInstaller not found. Install with: pip install pyinstaller"
        }
    }
    if ($PyInstallerCmd -eq "pyinstaller") {
        & pyinstaller @PyInstallerArgs
    } else {
        & $PyInstallerCmd -m PyInstaller @PyInstallerArgs
    }
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
} finally {
    Pop-Location
}

if (-not (Test-Path $DistExe)) {
    Write-Error "Expected exe not found: $DistExe (onedir output should be in $DistDir)"
}

New-Item -ItemType Directory -Force -Path $ResourcesDir | Out-Null
if (Test-Path $BackendResourceDir) { Remove-Item -Recurse -Force $BackendResourceDir }
Copy-Item -Recurse -Force $DistDir $BackendResourceDir
Write-Host "Copied to $BackendResourceDir"
Write-Host "Done. Run: npx tauri build"
Write-Host ""
