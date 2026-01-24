# Simple Frontend Startup Script
Write-Host "Starting Atlas Frontend..." -ForegroundColor Green

# Navigate to frontend
Set-Location "$PSScriptRoot\frontend"

Write-Host "Starting Next.js dev server..." -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop`n" -ForegroundColor Yellow

# Start server
npm run dev
