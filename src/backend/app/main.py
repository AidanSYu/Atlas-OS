"""Main FastAPI application entry point (Embedded Desktop Sidecar)."""
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.api.routes import router
from app.core.database import init_db
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize database on startup - FATAL on failure
init_db()
logger.info("SQLite database initialized successfully")


app = FastAPI(
    title="Atlas API - Agentic RAG Knowledge Engine",
    description="Embedded desktop sidecar: SQLite + Qdrant in-process + Two-Brain Swarm",
    version="2.0.0-sidecar",
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
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# GZip Compression - optimized for large JSON responses (Graph data)
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return proper error response."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "type": type(exc).__name__,
        },
    )


# Include routes
app.include_router(router)
logger.info("Routes included")


@app.on_event("startup")
async def startup_event():
    """Application startup: server accepts requests immediately, then loads services in background.

    Phase 1 (instant): Server is live and /health answers straight away.
    Phase 2 (background task): Heavy ML service imports + LLM model loading.
    """
    logger.info("Atlas Sidecar starting up (SQLite + embedded Qdrant)")
    app.state.startup_complete = False

    async def _background_startup():
        """Load all services and the default LLM model without blocking the event loop."""
        try:
            from app.api.routes import ensure_services
            from app.services.llm import get_llm_service

            logger.info("Initializing services (LLM, embeddings, GLiNER)...")
            # Service constructors are lightweight now (GLiNER loads lazily on first ingest).
            # Call directly on the event loop - no blocking I/O in __init__ paths.
            ensure_services()
            logger.info("All services initialized successfully")

            # Load default LLM model with GPU acceleration
            logger.info("Loading default LLM model with GPU acceleration...")
            llm_service = get_llm_service()
            model_name = await llm_service.initialize_default_model()
            if model_name:
                logger.info(f"Default model loaded: {model_name}")
                status = llm_service.get_status()
                logger.info(
                    f"LLM Status - Active Model: {status.get('active_model')}, "
                    f"Device: {status.get('device')}, GPU Layers: {status.get('gpu_layers')}"
                )
            else:
                logger.warning("No model loaded at startup - LLM will be unavailable")

            app.state.startup_complete = True
            logger.info("Ready for inference")
        except Exception as e:
            logger.error(f"Background startup failed: {e}", exc_info=True)
            logger.warning("Services will be initialized lazily on first request")
            app.state.startup_complete = True  # Mark complete even on error so status is accurate

    # Fire-and-forget: server is live instantly; models load in the background
    asyncio.create_task(_background_startup())


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown."""
    logger.info("Atlas Sidecar shutting down")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
