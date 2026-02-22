    # Atlas Development Setup

## Quick Start

### Option 1: Tauri Development (Recommended)
Run the full Tauri application with hot-reload:

```powershell
npm run tauri:dev
```

This will:
- Start the Next.js dev server on http://localhost:3001
- Launch the Tauri desktop window
- Enable hot-reload for both frontend and Rust code

### Option 2: Frontend Only
For UI development without the Tauri shell:

```powershell
cd src/frontend
npm run dev
```

Then open http://localhost:3001 in your browser.

### Option 3: Backend Only
To run just the backend API server:

```powershell
.\scripts\dev\run_backend.ps1
```

Backend will be available at http://localhost:8000

## Common Issues

### Black Screen in Tauri
**Cause**: Port mismatch or dev server not started
**Solution**: 
- Make sure port 3001 is free
- Check that Next.js starts successfully before Tauri window opens
- Look for errors in the terminal

### Port Already in Use
**Symptom**: "Port 3001 is in use"
**Solution**: Kill the process using port 3001:

```powershell
# Find process using port 3001
netstat -ano | findstr :3001

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### Build Errors
**Solution**: Clean and reinstall dependencies

```powershell
cd src/frontend
rm -rf node_modules .next
npm install
npm run build
```

## Development Workflow

1. **Make frontend changes**: Edit files in `src/frontend/`, hot-reload will update automatically
2. **Make backend changes**: Edit Python files, restart backend server manually
3. **Make Tauri changes**: Edit Rust files in `src/tauri/src/`, Tauri will rebuild

## Architecture

```
Atlas/
├── src/
│   ├── frontend/        # Next.js 14 app (port 3001)
│   ├── backend/         # FastAPI server (port 8000)
│   └── tauri/           # Rust desktop wrapper
├── scripts/
│   ├── build/           # Build scripts
│   └── dev/             # Development helpers
└── installers/          # Built executables
```

## Configuration Files

- `src/tauri/tauri.conf.json` - Tauri settings (ports, security, bundle)
- `src/frontend/package.json` - Frontend dependencies & scripts
- `src/backend/app/core/config.py` - Backend configuration
- `.env.local` - Environment variables (create from .env.example)

## Troubleshooting

### Frontend won't load
1. Check http://localhost:3001 works in browser
2. Verify `beforeDevCommand` in tauri.conf.json
3. Check browser console for CSP errors

### Backend connection errors
1. Ensure backend is running on port 8000
2. Check CORS settings in FastAPI
3. Verify CSP allows `http://localhost:8000` in tauri.conf.json

### Hot-reload not working
1. Restart the dev server
2. Clear `.next` cache: `rm -rf src/frontend/.next`
3. Check file watcher limits (Linux/Mac)

## Building for Production

```powershell
# Build installer (.exe and .msi)
npm run tauri:build

# Output location
.\installers\
```

This will:
1. Build the frontend (Next.js static export)
2. Build the backend (PyInstaller bundle)
3. Bundle everything into a Tauri installer

---

**Need help?** Check `CLAUDE.md` for project structure and conventions.
