"""Configuration settings for Atlas application (Embedded Desktop Sidecar)."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    # SQLite Configuration (embedded - no external server)
    DATABASE_PATH: str = "./atlas.db"
    
    @property
    def database_url(self) -> str:
        """Construct SQLite connection URL."""
        return f"sqlite:///{self.DATABASE_PATH}"
    
    # Qdrant Configuration (embedded - runs in-process via path mode)
    QDRANT_STORAGE_PATH: str = "./qdrant_storage"
    QDRANT_COLLECTION: str = "atlas_documents"
    
    # Model Storage (for bundled LLM and NER models)
    MODELS_DIR: str = "./models"
    
    # File Storage
    UPLOAD_DIR: str = "./data/uploads"
    
    # API Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    
    # Processing Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_RETRIEVAL: int = 5


settings = Settings()

# Ensure directories exist
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.MODELS_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.QDRANT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)