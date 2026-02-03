# Atlas Desktop App - Resource Bundling Guide

This directory contains bundled resources for the Atlas desktop application. When present, the app starts PostgreSQL and Qdrant from here so the app can run **standalone** (no Docker or external servers required).

## Directory Structure

```
resources/
├── postgres/           # PostgreSQL binaries (optional)
│   ├── bin/           # postgres.exe, initdb.exe, psql.exe, etc.
│   └── lib/           # DLLs (Windows)
├── qdrant/            # Qdrant vector database (optional)
│   └── qdrant.exe     # Qdrant binary (Windows: qdrant.exe)
└── README.md          # This file
```

**Backend sidecar** is built separately and placed in `src-tauri/binaries/` (see repo root `build-backend.ps1`).

## PostgreSQL Bundling

### Download PostgreSQL Embedded

For each platform, download the appropriate PostgreSQL binaries:

**Windows (x64):**
```
https://get.enterprisedb.com/postgresql/postgresql-16.1-1-windows-x64-binaries.zip
```

**macOS (Apple Silicon):**
```
https://get.enterprisedb.com/postgresql/postgresql-16.1-1-osx-arm64-binaries.zip
```

**macOS (Intel):**
```
https://get.enterprisedb.com/postgresql/postgresql-16.1-1-osx-x64-binaries.zip
```

**Linux (x64):**
```
https://get.enterprisedb.com/postgresql/postgresql-16.1-1-linux-x64-binaries.tar.gz
```

### Required Files

Extract and place the following in `resources/postgres/bin/`:
- `postgres` (or `postgres.exe` on Windows)
- `initdb` (or `initdb.exe`)
- `pg_ctl` (or `pg_ctl.exe`)
- Required shared libraries

### Initialization

On first run, the app will:
1. Copy the postgres binaries to the app data directory
2. Run `initdb` to create a new database cluster
3. Start PostgreSQL on a local port (default: 5432)
4. Create the `atlas_knowledge` database

## Qdrant Bundling

### Download Qdrant

Download pre-built Qdrant binaries:

**Windows:**
```
https://github.com/qdrant/qdrant/releases/download/v1.7.0/qdrant-x86_64-pc-windows-msvc.zip
```

**macOS (Apple Silicon):**
```
https://github.com/qdrant/qdrant/releases/download/v1.7.0/qdrant-aarch64-apple-darwin.tar.gz
```

**macOS (Intel):**
```
https://github.com/qdrant/qdrant/releases/download/v1.7.0/qdrant-x86_64-apple-darwin.tar.gz
```

**Linux:**
```
https://github.com/qdrant/qdrant/releases/download/v1.7.0/qdrant-x86_64-unknown-linux-gnu.tar.gz
```

### Required Files

Place the Qdrant binary in `resources/qdrant/`:
- `qdrant` (or `qdrant.exe` on Windows)

### Initialization

On first run, the app will:
1. Copy the Qdrant binary to the app data directory
2. Start Qdrant on a local port (default: 6333)
3. Create storage directory for vector data

## Size Estimates

| Component | Approximate Size |
|-----------|-----------------|
| PostgreSQL binaries | ~50MB |
| Qdrant binary | ~30MB |
| LLM Model (Llama 3 8B Q4) | ~4.7GB |
| Embedding Model | ~275MB |
| GLiNER Model | ~50MB |
| **Total** | **~5.1GB** |

## Build and bundle (standalone app)

**Windows (PowerShell, from repo root):**

1. **Backend (required for sidecar):**  
   `.\build-backend.ps1`  
   Builds the Python backend with PyInstaller and copies the exe to `src-tauri/binaries/atlas-backend-x86_64-pc-windows-msvc.exe`.

2. **PostgreSQL + Qdrant (optional, for fully standalone):**  
   `.\scripts\download-bundle-resources.ps1`  
   Downloads PostgreSQL and Qdrant into `src-tauri/resources/`. If you skip this, the app still runs but expects Postgres and Qdrant to be running elsewhere (e.g. Docker).

3. **Build Tauri app:**  
   `npm run tauri:build`  
   (or `npm run build:backend` then `npx tauri build`)

**Startup order:** When resources are present, the app starts Postgres → Qdrant → Backend automatically and stops them on exit.

## Platform-Specific Notes

### Windows
- Use `.exe` extensions for all binaries
- May need Visual C++ Redistributable

### macOS
- Code signing may be required for distribution
- Universal binaries recommended for both Intel and Apple Silicon

### Linux
- Ensure GLIBC compatibility
- May need additional shared libraries
