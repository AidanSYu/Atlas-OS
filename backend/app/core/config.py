"""Configuration settings for Atlas application."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    # PostgreSQL Configuration
    POSTGRES_HOST: str = "db_graph"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "atlas_knowledge"
    POSTGRES_USER: str = "atlas"
    POSTGRES_PASSWORD: str = "atlas_secure_password"
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    # Qdrant Configuration
    QDRANT_HOST: str = "db_vector"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "atlas_documents"
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # File Storage
    UPLOAD_DIR: str = "/app/data/uploads"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Processing Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_RETRIEVAL: int = 5


settings = Settings()

# Ensure directories exist
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
