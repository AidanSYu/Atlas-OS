"""Reranking service using FlashRank (SOTA lightweight cross-encoder)."""
from typing import List, Dict, Any
import logging
import asyncio
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)

class RerankService:
    """Service for reranking retrieved documents using FlashRank."""
    
    _instance = None
    
    def __init__(self):
        self._ranker = None
        self._model_name = "ms-marco-TinyBERT-L-2-v2" # Ultra-lightweight (4MB)
        self._lock = asyncio.Lock()
        
    async def _load_model(self):
        """Lazy load the FlashRank model."""
        if self._ranker:
            return

        try:
            from flashrank import Ranker, RerankRequest
            # Initialize Ranker (downloads model to cache if needed)
            # Uses onnxruntime for speed on CPU
            logger.info(f"Loading FlashRank model: {self._model_name}")
            self._ranker = Ranker(model_name=self._model_name, cache_dir=str(Path(settings.MODELS_DIR) / "flashrank"))
            logger.info("FlashRank model loaded successfully")
        except ImportError:
            logger.error("flashrank not installed. Reranking will be disabled.")
            self._ranker = "DISABLED"
        except Exception as e:
            logger.error(f"Failed to load FlashRank: {e}")
            self._ranker = "DISABLED"

    async def rerank(self, query: str, documents: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """Rerank a list of documents based on query relevance.
        
        Args:
            query: The search query
            documents: List of docs, must have 'text' and 'metadata' keys
            top_n: Number of documents to return
            
        Returns:
            Reranked and sliced list of documents
        """
        if not settings.ENABLE_RERANKING:
            return documents[:top_n]
            
        async with self._lock:
            if not self._ranker:
                await self._load_model()
                
        if self._ranker == "DISABLED":
            return documents[:top_n]
            
        if not documents:
            return []
            
        try:
            from flashrank import RerankRequest
            
            # FlashRank expects list of dicts with "id", "text", "meta"
            passages = []
            for i, doc in enumerate(documents):
                passages.append({
                    "id": i,
                    "text": doc.get("text", ""),
                    "meta": doc.get("metadata", {}) # Pass through metadata
                })
                
            request = RerankRequest(query=query, passages=passages)
            results = self._ranker.rerank(request)
            
            # Map back to our document format
            reranked_docs = []
            for r in results:
                # FlashRank returns dict with 'id', 'text', 'meta', 'score'
                original_idx = r["id"]
                original_doc = documents[original_idx]

                # Preserve relevance_score key for downstream compatibility
                reranked_docs.append({
                    **original_doc,
                    "relevance_score": r["score"],
                    "rerank_score": r["score"],
                    "original_score": original_doc.get("relevance_score", original_doc.get("score"))
                })

            # Sort by relevance_score
            reranked_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            return reranked_docs[:top_n]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return documents[:top_n] # Fallback to original order

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

def get_rerank_service():
    return RerankService.get_instance()
