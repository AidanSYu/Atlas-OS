"""Main FastAPI application entry point."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import logging
from pathlib import Path

import app.api.routes as routes_module
from app.api.routes import router
from app.core.database import init_db
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize database on startup
try:
    init_db()
    logger.info("✓ Database initialized successfully")
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")


app = FastAPI(
    title="Atlas API - AI-Native Knowledge Layer",
    description="Scalable knowledge substrate for AI retrieval and reasoning",
    version="2.0.0"
)
logger.info("✓ FastAPI app created")


# CORS Configuration - FIXED: More restrictive for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Development frontend
        "http://localhost:8000",  # Development API
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        # Add production origins here when deploying
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600  # Cache preflight requests
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
try:
    app.include_router(router)
    logger.info("✓ Routes included")
except Exception as e:
    logger.error(f"❌ Failed to include routes: {e}", exc_info=True)


# PERFORMANCE FIX: Non-blocking startup event
@app.on_event("startup")
async def startup_event():
    """Start background filesystem sync without blocking startup."""
    logger.info("🚀 Application startup - launching background sync task")
    asyncio.create_task(sync_filesystem_to_db())


# ---------------------------------------------------------
# STARTUP SYNCHRONIZATION
# ---------------------------------------------------------

async def sync_filesystem_to_db() -> None:
    """
    Background task to sync files in UPLOAD_DIR with the database.
    Detects PDFs on disk that are missing from the DB and ingests them.
    """
    logger.info("🔄 Starting filesystem synchronization...")

    # Ensure services are initialized (reuse global instances from routes.py)
    routes_module.ensure_services()
    ingest_service = routes_module.ingestion_service

    if not ingest_service:
        logger.error("❌ Ingestion service failed to initialize. Skipping sync.")
        return

    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.exists():
        logger.info(f"📂 Upload directory {upload_dir} does not exist. Creating...")
        upload_dir.mkdir(parents=True, exist_ok=True)
        return

    pdf_files = list(upload_dir.glob("*.pdf"))
    logger.info(f"📂 Found {len(pdf_files)} PDFs in upload directory.")

    synced_count = 0
    for file_path in pdf_files:
        try:
            # Safe to call for every file: ingest_document deduplicates by file hash
            result = await ingest_service.ingest_document(str(file_path), file_path.name)

            if result.get("status") == "success":
                logger.info(f"✅ Auto-ingested missing file: {file_path.name}")
                synced_count += 1
            elif result.get("status") == "duplicate":
                # Already in DB; nothing to do
                continue
            else:
                logger.warning(f"⚠️ Sync result for {file_path.name}: {result.get('status')}")

        except Exception as e:
            logger.error(f"❌ Failed to sync file {file_path.name}: {e}")

    if synced_count > 0:
        logger.info(f"✨ Synchronization complete. Added {synced_count} new documents to the Knowledge Graph.")
    else:
        logger.info("✅ System is up to date. No new files found.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT
    )

