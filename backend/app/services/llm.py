"""
LLM Service - Bundled LLM and embedding service using llama-cpp-python.

Replaces Ollama for standalone desktop app deployment.
Uses:
- llama-cpp-python for text generation (Llama 3 8B GGUF)
- sentence-transformers for embeddings (nomic-embed-text-v1.5)
"""
from pathlib import Path
from typing import List, Optional
import logging
import asyncio
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy imports to avoid loading heavy models at import time
_llm_instance = None
_embedder_instance = None


class LLMService:
    """Bundled LLM service using llama-cpp-python and sentence-transformers.
    
    This service provides:
    - Text generation using Llama 3 8B (quantized GGUF)
    - Text embeddings using nomic-embed-text-v1.5
    
    Models are loaded from the MODELS_DIR specified in settings.
    """
    
    _instance: Optional['LLMService'] = None
    
    def __init__(self, models_dir: Optional[Path] = None):
        """Initialize LLM service.
        
        Args:
            models_dir: Path to directory containing models.
                       Defaults to settings.MODELS_DIR.
        """
        self.models_dir = Path(models_dir or settings.MODELS_DIR)
        self._llm = None
        self._embedder = None
        self._embedding_dim = 768  # nomic-embed-text dimension
        
        logger.info(f"LLMService initializing with models_dir: {self.models_dir}")
    
    def _load_llm(self):
        """Load the LLM model (lazy loading)."""
        if self._llm is not None:
            return
        
        try:
            from llama_cpp import Llama
        except ImportError:
            logger.warning(
                "llama-cpp-python not installed. Text generation will use fallback. "
                "Install with: pip install llama-cpp-python"
            )
            self._llm = "FALLBACK"  # Mark as fallback mode
            return
        
        # Look for GGUF model file
        model_patterns = [
            "llama-3-8b-instruct*.gguf",
            "Meta-Llama-3-8B-Instruct*.gguf",
            "*.gguf"
        ]
        
        model_path = None
        for pattern in model_patterns:
            matches = list(self.models_dir.glob(pattern))
            if matches:
                model_path = matches[0]
                break
        
        if not model_path or not model_path.exists():
            logger.warning(
                f"LLM model not found in {self.models_dir}. Using fallback mode. "
                f"Download a .gguf model for full functionality."
            )
            self._llm = "FALLBACK"
            return
        
        logger.info(f"Loading LLM from {model_path}")
        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=4096,
            n_gpu_layers=-1,  # Use all GPU layers if available
            verbose=False,
            n_threads=4
        )
        logger.info(f"LLM loaded successfully from {model_path}")
    
    def _load_embedder(self):
        """Load the embedding model (lazy loading)."""
        if self._embedder is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        # Look for embedding model directory
        embed_patterns = [
            "nomic-embed-text-v1.5",
            "nomic-embed-text*",
        ]
        
        embed_path = None
        for pattern in embed_patterns:
            matches = list(self.models_dir.glob(pattern))
            if matches:
                embed_path = matches[0]
                break
        
        if embed_path and embed_path.exists():
            logger.info(f"Loading embedding model from {embed_path}")
            self._embedder = SentenceTransformer(str(embed_path))
        else:
            # Fall back to downloading from HuggingFace (first run)
            logger.warning(
                f"Embedding model not found in {self.models_dir}. "
                "Downloading from HuggingFace..."
            )
            self._embedder = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5")
        
        logger.info("Embedding model loaded successfully")
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None
    ) -> str:
        """Generate text completion.
        
        Args:
            prompt: The prompt to complete
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            stop: List of stop sequences
            
        Returns:
            Generated text string
        """
        # Lazy load model
        if self._llm is None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_llm)
        
        # Handle fallback mode (no llama-cpp-python or no model)
        if self._llm == "FALLBACK":
            logger.warning("LLM generation in fallback mode - returning placeholder response")
            return (
                "I cannot generate a detailed response because the LLM model is not available. "
                "Please install llama-cpp-python and download a GGUF model file. "
                "However, I can confirm the retrieval system found relevant documents."
            )
        
        if stop is None:
            stop = ["</s>", "Human:", "User:", "\n\nHuman:", "\n\nUser:"]
        
        # Run generation in executor to not block event loop
        loop = asyncio.get_running_loop()
        
        def _generate():
            output = self._llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
                echo=False
            )
            return output["choices"][0]["text"].strip()
        
        return await loop.run_in_executor(None, _generate)
    
    async def embed(self, text: str) -> List[float]:
        """Generate embedding vector for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        # Lazy load model
        if self._embedder is None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_embedder)
        
        # Run embedding in executor to not block event loop
        loop = asyncio.get_running_loop()
        
        def _embed():
            return self._embedder.encode(text).tolist()
        
        return await loop.run_in_executor(None, _embed)
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # Lazy load model
        if self._embedder is None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_embedder)
        
        # Run batch embedding in executor
        loop = asyncio.get_running_loop()
        
        def _embed_batch():
            return self._embedder.encode(texts).tolist()
        
        return await loop.run_in_executor(None, _embed_batch)
    
    @property
    def embedding_dimension(self) -> int:
        """Return the embedding dimension."""
        return self._embedding_dim
    
    @classmethod
    def get_instance(cls) -> 'LLMService':
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Convenience function for getting the service
def get_llm_service() -> LLMService:
    """Get the singleton LLM service instance."""
    return LLMService.get_instance()
