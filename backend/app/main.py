"""Main FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.database import init_db
from app.core.config import settings

# Initialize database on startup
try:
    init_db()
    print("✓ Database initialized")
except Exception as e:
    print(f"Warning: Database initialization failed: {e}")

app = FastAPI(
    title="Atlas API - AI-Native Knowledge Layer",
    description="Scalable knowledge substrate for AI retrieval and reasoning",
    version="2.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT
    )
