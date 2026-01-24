from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    # Database backend: "postgres" (default) or "sqlite"
    DB_BACKEND: str = "postgres"
    SQLITE_PATH: str = "./data/atlas.db"
    # PostgreSQL Configuration
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "atlas_knowledge"
    POSTGRES_USER: str = "atlas"
    POSTGRES_PASSWORD: str = "atlas_secure_password"
    
    @property
    def database_url(self) -> str:
        if self.DB_BACKEND.lower() == "sqlite":
            return f"sqlite:///{self.SQLITE_PATH}"
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Qdrant Configuration
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "atlas_documents"
    VECTOR_BACKEND: str = "qdrant"  # "qdrant" (default) or "local"
    LOCAL_VECTOR_PATH: str = "./data/local_vectors.json"
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"  # Small 1B model for testing
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # File Storage
    UPLOAD_DIR: str = "./data/uploads"
    
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
Path(settings.SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
