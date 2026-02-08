# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Atlas Backend.

This bundles the Python backend as a one-directory (onedir) bundle for use from
Tauri resources. Onedir allows fast incremental builds (only changed files are
replaced; torch/DLLs are left in place).

To build:
    cd backend
    pyinstaller atlas.spec

The output will be dist/atlas-backend/ containing atlas-backend.exe and deps.
Copy the entire folder to src-tauri/resources/atlas-backend/ (see build-backend.ps1).
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

# Collect models from repo root (models/) when -IncludeModels is set
models_dir = backend_dir.parent / 'models'
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
    
    # SQLAlchemy (SQLite embedded)
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    
    # Pydantic
    'pydantic',
    'pydantic_settings',
    
    # ML Libraries
    'torch',
    'transformers',
    'sentence_transformers',
    'gliner',
    'llama_cpp',
    
    # Qdrant (embedded mode)
    'qdrant_client',
    'qdrant_client.models',
    'qdrant_client.local',
    
    # PDF Processing
    'pypdf',
    'pdfplumber',
    
    # Agentic RAG - Two-Brain Swarm
    'langgraph',
    'langgraph.graph',
    'networkx',
    
    # Other dependencies
    'aiofiles',
    'python_multipart',
    'httptools',
    'uvloop',
    'watchfiles',
    'websockets',
]

# Binaries: collect llama_cpp's native extension (.pyd/.so) so the LLM works in the bundle
# (GLiNER/sentence_transformers work because they're pure Python + torch; llama_cpp is C++.)
try:
    from PyInstaller.utils.hooks import collect_dynamic_libs
    binaries = collect_dynamic_libs('llama_cpp', search_dirs=None)
except Exception:
    binaries = []

# Platform-specific extras if needed
if sys.platform == 'win32':
    pass
elif sys.platform == 'darwin':
    pass
else:
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

# Onedir: executable + deps in a folder; Tauri runs exe with current_dir = folder
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='atlas-backend',
)
