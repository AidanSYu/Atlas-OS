# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Atlas Backend.

This bundles the Python backend as a single executable (onefile) for use as a Tauri sidecar.

To build:
    cd backend
    pyinstaller atlas.spec

The output will be dist/atlas-backend.exe (Windows) or dist/atlas-backend (Unix).
Copy to src-tauri/binaries/ with the Tauri target triple name, e.g.:
  atlas-backend-x86_64-pc-windows-msvc.exe (Windows)
  atlas-backend-x86_64-apple-darwin (macOS)
  atlas-backend-x86_64-unknown-linux-gnu (Linux)
"""
import os
import sys
from pathlib import Path

# Get the backend directory
backend_dir = Path(SPECPATH)

# Collect all app source files
app_data = [
    (str(backend_dir / 'app'), 'app'),
]

# Collect models if they exist
models_dir = backend_dir / 'models'
if os.environ.get("ATLAS_INCLUDE_MODELS") == "1" and models_dir.exists():
    app_data.append((str(models_dir), 'models'))

# Hidden imports for dynamic imports
hidden_imports = [
    # Uvicorn
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    
    # FastAPI / Starlette
    'fastapi',
    'starlette',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    
    # SQLAlchemy
    'sqlalchemy',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.postgresql.psycopg2',
    
    # Pydantic
    'pydantic',
    'pydantic_settings',
    
    # ML Libraries
    'torch',
    'transformers',
    'sentence_transformers',
    'gliner',
    'llama_cpp',
    
    # Qdrant
    'qdrant_client',
    'qdrant_client.models',
    
    # PDF Processing
    'pypdf',
    'pdfplumber',
    
    # Other dependencies
    'aiofiles',
    'python_multipart',
    'httptools',
    'uvloop',
    'watchfiles',
    'websockets',
]

# Binaries to include (torch libraries)
binaries = []

# Platform-specific binaries
if sys.platform == 'win32':
    # Windows-specific
    pass
elif sys.platform == 'darwin':
    # macOS-specific
    pass
else:
    # Linux-specific
    pass


a = Analysis(
    [str(backend_dir / 'run_server.py')],
    pathex=[str(backend_dir)],
    binaries=binaries,
    datas=app_data,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'cv2',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Onefile: single executable for Tauri sidecar
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='atlas-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
