# Build Atlas backend with PyInstaller and copy to src-tauri/binaries for Tauri sidecar.
# Run from repo root. Requires: Python with PyInstaller, backend dependencies installed.
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
$BinariesDir = Join-Path (Join-Path $RepoRoot "src-tauri") "binaries"

# Tauri sidecar naming: binary-name{-target-triple}{.ext}
# https://tauri.app/v1/guides/building/sidecar
$TargetTriples = @{
    "win32"   = "x86_64-pc-windows-msvc"
    "darwin"  = "x86_64-apple-darwin"   # Intel Mac; use aarch64-apple-darwin for ARM
    "linux"   = "x86_64-unknown-linux-gnu"
}
$ExeNames = @{
    "win32"   = "atlas-backend.exe"
    "darwin"  = "atlas-backend"
    "linux"   = "atlas-backend"
}

# Detect platform
if ($env:OS -eq "Windows_NT") { $Platform = "win32" }
elseif ($IsMacOS) { $Platform = "darwin" }
else { $Platform = "linux" }

$Triple = $TargetTriples[$Platform]
$SidecarName = "atlas-backend-$Triple"
if ($Platform -eq "win32") { $SidecarName += ".exe" }

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

$DistExe = Join-Path (Join-Path $BackendDir "dist") $ExeNames[$Platform]
$SidecarDest = Join-Path $BinariesDir $SidecarName

if ($SkipIfUnchanged -and -not $Force -and (Test-Path $DistExe)) {
    $sourceLatest = Get-LatestWriteTime @(
        (Join-Path $BackendDir "app"),
        (Join-Path $BackendDir "run_server.py"),
        (Join-Path $BackendDir "atlas.spec"),
        (Join-Path $BackendDir "requirements.txt")
    )
    if ($sourceLatest -and $sourceLatest -le (Get-Item $DistExe).LastWriteTime) {
        Write-Host "Skipping PyInstaller (backend unchanged)."
        New-Item -ItemType Directory -Force -Path $BinariesDir | Out-Null
        Copy-Item -Force $DistExe $SidecarDest
        Write-Host "Copied to $SidecarDest"
        Write-Host "Done. Run: npx tauri build"
        Write-Host ""
        return
    }
}

Write-Host "Building Atlas backend (PyInstaller onefile) for $Platform ($Triple)..."

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
    Write-Error "Expected exe not found: $DistExe"
}

New-Item -ItemType Directory -Force -Path $BinariesDir | Out-Null
Copy-Item -Force $DistExe $SidecarDest
Write-Host "Copied to $SidecarDest"
Write-Host "Done. Run: npx tauri build"
Write-Host ""
