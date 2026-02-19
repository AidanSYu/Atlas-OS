"""Configuration settings for Atlas application (Embedded Desktop Sidecar)."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path


def _get_models_dir() -> str:
    """Get the absolute path to the models directory."""
    # config.py is at: project/backend/app/core/config.py
    # So parent.parent.parent gets us to project root
    backend_dir = Path(__file__).resolve().parent.parent.parent
    return str(backend_dir / "models")


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
    # Uses absolute path relative to project root
    MODELS_DIR: str = Field(default_factory=_get_models_dir)
    
    # File Storage
    UPLOAD_DIR: str = "./data/uploads"
    
    # API Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    
    # Processing Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_RETRIEVAL: int = 5

    # Agent Reasoning Configuration (Phase A1: Navigator 2.0)
    ENABLE_NAVIGATOR_REFLECTION: bool = True  # Enable multi-turn reflection loops
    MAX_REFLECTION_ITERATIONS: int = 3        # Max reflection cycles (prevents infinite loops)
    NAVIGATOR_CONFIDENCE_THRESHOLD: float = 0.75  # Auto-pass threshold for high confidence

    # Cortex Configuration (Phase A2: Cortex 2.0)
    ENABLE_CORTEX_CROSSCHECK: bool = True  # Enable cross-checking and contradiction detection
    CORTEX_NUM_SUBTASKS: int = 5           # Number of sub-tasks to decompose query into

    # Prompt Engineering Configuration (Phase A3)
    USE_PROMPT_TEMPLATES: bool = True      # Enable few-shot prompt templates
    ENABLE_OUTPUT_VALIDATION: bool = True  # Enable structured output validation with retries
    MAX_VALIDATION_RETRIES: int = 2        # Max retries for malformed LLM outputs

    # RAG Optimization Configuration (Phase B)
    ENABLE_RERANKING: bool = True          # Enable FlashRank reranking
    RERANK_TOP_N: int = 5                  # Number of chunks to keep after reranking
    GRAPH_CACHE_TTL: int = 300             # Cache duration for graph queries (seconds)

    # Phase B2: Document Parsing
    USE_DOCLING: bool = True               # Enable Docling VLM parsing (fallback: pdfplumber)

    # Phase B3: Semantic Chunking
    USE_SEMANTIC_CHUNKING: bool = True     # Enable semantic chunking (fallback: fixed-size)
    SEMANTIC_CHUNK_TOKENS: int = 512       # Target tokens per semantic chunk

    # Phase B4: RAPTOR Hierarchical Summarization
    USE_RAPTOR: bool = True                # Enable RAPTOR hierarchy on ingestion
    RAPTOR_CLUSTERS: int = 5              # Number of L1 clusters per document

    # Atlas 3.0: LLM Performance Configuration
    LLM_CONTEXT_SIZE: int = 8192           # Context window (tokens). 8192 for 7B, 4096 for 3B if OOM
    LLM_N_BATCH: int = 512                 # Batch size for prompt processing
    LLM_USE_MLOCK: bool = True             # Keep model weights pinned in RAM (prevents swapping)
    LLM_VERBOSE: bool = False              # Disable verbose llama.cpp logging in production


settings = Settings()

# Ensure directories exist
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.MODELS_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.QDRANT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)