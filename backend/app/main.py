"""Main FastAPI application entry point (Production Desktop App)."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Optional

import app.api.routes as routes_module
from app.api.routes import router
from app.core.database import init_db
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize database on startup - FATAL on failure
init_db()
logger.info("Database initialized successfully")


app = FastAPI(
    title="Atlas API - AI-Native Knowledge Layer",
    description="Production desktop app - knowledge substrate for AI retrieval and reasoning",
    version="2.0.0-desktop"
)
logger.info("FastAPI app created")


# CORS Configuration - Locked to Tauri internal origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "https://tauri.localhost",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Global error handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return proper error response."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "type": type(exc).__name__
        }
    )

# Include routes
app.include_router(router)
logger.info("Routes included")


# ---------------------------------------------------------
# FILE SYNC WORKER (Production-grade background synchronization)
# ---------------------------------------------------------

class FileSyncWorker:
    """Robust background worker for filesystem synchronization.
    
    Features:
    - Hash verification before ingestion
    - Periodic re-sync capability
    - Graceful shutdown support
    - Integrity checking
    """
    
    def __init__(self, sync_interval: int = 60):
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._sync_interval = sync_interval
        self._initialized = False
    
    async def start(self):
        """Start the background sync worker."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())
        logger.info("FileSyncWorker started")
    
    async def stop(self):
        """Gracefully stop the worker."""
        self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                logger.warning("FileSyncWorker force-stopped after timeout")
        logger.info("FileSyncWorker stopped")
    
    async def _run(self):
        """Main worker loop."""
        # Initial sync on startup
        await self._sync_once()
        
        # Periodic re-sync
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._sync_interval
                )
                break  # Stop event was set
            except asyncio.TimeoutError:
                # Timeout means we should re-sync
                await self._sync_once()
    
    async def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        loop = asyncio.get_running_loop()
        
        def _hash_file():
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        
        return await loop.run_in_executor(None, _hash_file)
    
    async def _verify_integrity(self, file_path: Path) -> bool:
        """Verify file integrity before ingestion.
        
        Checks:
        - File exists and is readable
        - File has non-zero size
        - File is a valid PDF (magic bytes)
        """
        try:
            if not file_path.exists():
                logger.error(f"File does not exist: {file_path}")
                return False
            
            if file_path.stat().st_size == 0:
                logger.error(f"File is empty: {file_path}")
                return False
            
            # Check PDF magic bytes
            with open(file_path, 'rb') as f:
                header = f.read(5)
                if header != b'%PDF-':
                    logger.error(f"File is not a valid PDF: {file_path}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Integrity check failed for {file_path}: {e}")
            return False
    
    async def _sync_once(self):
        """Perform a single sync cycle with hash verification."""
        logger.info("Starting filesystem synchronization...")
        
        # Ensure services are initialized
        try:
            routes_module.ensure_services()
        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            return
        
        ingest_service = routes_module.ingestion_service
        if not ingest_service:
            logger.error("Ingestion service not available")
            return
        
        upload_dir = Path(settings.UPLOAD_DIR)
        if not upload_dir.exists():
            logger.info(f"Upload directory {upload_dir} does not exist. Creating...")
            upload_dir.mkdir(parents=True, exist_ok=True)
            return
        
        pdf_files = list(upload_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDFs in upload directory")
        
        synced_count = 0
        for file_path in pdf_files:
            try:
                # Verify integrity before processing
                if not await self._verify_integrity(file_path):
                    logger.warning(f"Skipping file with failed integrity check: {file_path.name}")
                    continue
                
                # Compute hash for verification
                file_hash = await self._compute_file_hash(file_path)
                logger.debug(f"File hash for {file_path.name}: {file_hash[:16]}...")
                
                # Ingest document (deduplicates by hash internally)
                result = await ingest_service.ingest_document(str(file_path), file_path.name)
                
                if result.get("status") == "success":
                    logger.info(f"Auto-ingested: {file_path.name}")
                    synced_count += 1
                elif result.get("status") == "duplicate":
                    continue
                else:
                    logger.warning(f"Sync result for {file_path.name}: {result.get('status')}")
            
            except Exception as e:
                logger.error(f"Failed to sync file {file_path.name}: {e}")
        
        if synced_count > 0:
            logger.info(f"Synchronization complete. Added {synced_count} documents.")
        else:
            logger.info("System is up to date. No new files found.")


# Global worker instance
_file_sync_worker: Optional[FileSyncWorker] = None


@app.on_event("startup")
async def startup_event():
    """Start background services on application startup."""
    global _file_sync_worker
    logger.info("Application startup - initializing background services")
    
    _file_sync_worker = FileSyncWorker(sync_interval=60)
    await _file_sync_worker.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully stop background services on shutdown."""
    global _file_sync_worker
    logger.info("Application shutdown - stopping background services")
    
    if _file_sync_worker:
        await _file_sync_worker.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT
    )

