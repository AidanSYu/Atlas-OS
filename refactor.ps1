# ==========================================
# Project Atlas Refactor Script
# ==========================================
# This script automates the restructuring of the codebase into a modular src-layout.
# It handles:
# 1. Directory creation (src, config, scripts, tests, installers)
# 2. File migration
# 3. Cleanup of temporary files (Commented out by default)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

Write-Host "Starting Project Atlas Refactor..." -ForegroundColor Cyan

# --- 1. Create Directory Structure ---
$Dirs = @(
    "src\backend",
    "src\frontend",
    "src\tauri",
    "config",
    "scripts\build",
    "scripts\dev",
    "scripts\setup",
    "tests\backend",
    "installers",
    "doc"
)

foreach ($Dir in $Dirs) {
    if (-not (Test-Path "$Root\$Dir")) {
        New-Item -ItemType Directory -Path "$Root\$Dir" -Force | Out-Null
        Write-Host "Created: $Dir" -ForegroundColor Green
    }
}

# --- 2. Move Configuration Files ---
$ConfigMoves = @{
    ".env"                            = "config\.env";
    ".env.example"                    = "config\.env.example";
    ".aider.conf.yml"                 = "config\.aider.conf.yml";
    ".aiderignore"                    = "config\.aiderignore";
    "tools\aider_model_metadata.json" = "config\aider_model_metadata.json";
}

Write-Host "`nMoving Configuration..." -ForegroundColor Yellow
foreach ($Src in $ConfigMoves.Keys) {
    if (Test-Path "$Root\$Src") {
        Move-Item -Path "$Root\$Src" -Destination "$Root\$($ConfigMoves[$Src])" -Force
        Write-Host "Moved: $Src -> $($ConfigMoves[$Src])" -ForegroundColor Gray
    }
}

# Move Config Folder Prompts if exists
if (Test-Path "$Root\tools\prompts") {
    Move-Item -Path "$Root\tools\prompts" -Destination "$Root\config\prompts" -Force
    Write-Host "Moved: tools\prompts -> config\prompts" -ForegroundColor Gray
}

# --- 3. Move Scripts ---
$ScriptMoves = @{
    "build-backend.ps1"             = "scripts\build\build-backend.ps1";
    "backend\atlas.spec"            = "scripts\build\atlas.spec";
    "tools\launch_hybrid_aider.ps1" = "scripts\dev\launch_hybrid_aider.ps1";
    "tools\launch_hybrid_aider.sh"  = "scripts\dev\launch_hybrid_aider.sh";
    "tools\check_keys.py"           = "scripts\dev\check_keys.py";
    "tools\audit.sh"                = "scripts\dev\audit.sh";
    "setup-prereqs.ps1"             = "scripts\setup\setup_project.ps1"; # Consolidated base
}

Write-Host "`nMoving Scripts..." -ForegroundColor Yellow
foreach ($Src in $ScriptMoves.Keys) {
    if (Test-Path "$Root\$Src") {
        Move-Item -Path "$Root\$Src" -Destination "$Root\$($ScriptMoves[$Src])" -Force
        Write-Host "Moved: $Src -> $($ScriptMoves[$Src])" -ForegroundColor Gray
    }
}

# --- 4. Move Source Code ---
# To avoid moving the newly created src folder into itself, we move contents specificially
Write-Host "`nMoving Source Code..." -ForegroundColor Yellow

# Backend
if (Test-Path "$Root\backend") {
    # Check if we are accidentally moving our new src
    $Items = Get-ChildItem -Path "$Root\backend"
    foreach ($Item in $Items) {
        if ($Item.Name -ne "src") {
            Move-Item -Path $Item.FullName -Destination "$Root\src\backend" -Force
        }
    }
    Remove-Item -Path "$Root\backend" -Force
    Write-Host "Moved: backend/* -> src/backend/" -ForegroundColor Gray
}

# Frontend
if (Test-Path "$Root\frontend") {
    $Items = Get-ChildItem -Path "$Root\frontend"
    foreach ($Item in $Items) {
        Move-Item -Path $Item.FullName -Destination "$Root\src\frontend" -Force
    }
    Remove-Item -Path "$Root\frontend" -Force
    Write-Host "Moved: frontend/* -> src/frontend/" -ForegroundColor Gray
}

# Tauri
if (Test-Path "$Root\src-tauri") {
    Get-ChildItem -Path "$Root\src-tauri" | Move-Item -Destination "$Root\src\tauri" -Force
    Remove-Item -Path "$Root\src-tauri" -Force
    Write-Host "Moved: src-tauri/* -> src/tauri/" -ForegroundColor Gray
}

# Move specific tool to backend
if (Test-Path "$Root\tools\atlas_mcp_server.py") {
    Move-Item -Path "$Root\tools\atlas_mcp_server.py" -Destination "$Root\src\backend\tools" -Force
    Write-Host "Moved: tools\atlas_mcp_server.py -> src\backend\tools\" -ForegroundColor Gray
}

# --- 5. Cleanup & Deletion (Commented Out for Safety) ---
Write-Host "`nCleanup Candidates (Uncomment in script to enable deletetion):" -ForegroundColor Magenta
$Garbage = @(
    "$Root\src\backend\test_gpu.py",
    "$Root\src\backend\test_output.txt",
    "$Root\tools\key_check.log",
    "$Root\tools\test.sh",
    "$Root\tools\profile.py",
    "$Root\tools\setup_env.sh" # Merging into setup_project.ps1
)

foreach ($Item in $Garbage) {
    if (Test-Path $Item) {
        # Uncomment the line below to enable deletion
        # Remove-Item -Path $Item -Force
        Write-Host "Recommended Delete: $Item" -ForegroundColor Red
    }
}

# Remove empty tools folder if empty
if ((Test-Path "$Root\tools") -and (@(Get-ChildItem "$Root\tools").Count -eq 0)) {
    Remove-Item "$Root\tools" -Force
    Write-Host "Removed empty 'tools' directory" -ForegroundColor Green
}

Write-Host "`nRefactor Complete! Please update your .gitignore and IDE paths." -ForegroundColor Cyan
Write-Host "IMPORTANT: You may need to update 'tauri.conf.json' to point to '../frontend/out' or '../frontend/dist' depending on your new relative paths." -ForegroundColor Yellow
