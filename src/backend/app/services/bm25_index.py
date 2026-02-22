"""
BM25 Index Service - Sparse keyword retrieval for hybrid search.

Atlas 3.0 Phase 2: Integrates bm25s for fast BM25 scoring alongside
vector search. Results are fused using Reciprocal Rank Fusion (RRF).

Usage:
    bm25 = BM25IndexService.get_instance()
    bm25.add_documents(doc_id, chunks)  # Called during ingestion
    results = bm25.search(query, top_k=20)  # Called during retrieval
"""
import logging
from typing import Dict, List, Optional, Any
import threading

logger = logging.getLogger(__name__)

# Lazy import bm25s (may not be installed)
_BM25S_AVAILABLE = False
try:
    import bm25s
    _BM25S_AVAILABLE = True
except ImportError:
    logger.info("bm25s not installed - BM25 sparse retrieval disabled")


class BM25IndexService:
    """In-memory BM25 index for sparse keyword retrieval.

    Maintains a corpus of document chunks and provides fast keyword-based
    search to complement vector similarity search. Results are typically
    fused with vector search results using RRF before reranking.
    """

    _instance: Optional['BM25IndexService'] = None

    def __init__(self):
        self._corpus_texts: List[str] = []
        self._corpus_metadata: List[Dict[str, Any]] = []
        self._retriever = None
        self._lock = threading.Lock()
        self._dirty = True  # Index needs rebuilding
        logger.info("BM25IndexService initialized")

    @classmethod
    def get_instance(cls) -> 'BM25IndexService':
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def is_available() -> bool:
        """Check if bm25s is installed."""
        return _BM25S_AVAILABLE

    def add_documents(
        self,
        doc_id: str,
        chunks: List[Dict[str, Any]],
    ):
        """Add document chunks to the BM25 corpus.

        Args:
            doc_id: Document ID these chunks belong to.
            chunks: List of chunk dicts with 'text' and 'metadata' keys.
        """
        with self._lock:
            for chunk in chunks:
                text = chunk.get("text", "")
                if not text.strip():
                    continue
                self._corpus_texts.append(text)
                self._corpus_metadata.append({
                    "doc_id": doc_id,
                    "chunk_index": chunk.get("chunk_index", 0),
                    "page_number": chunk.get("page_number"),
                    "metadata": chunk.get("metadata", {}),
                })
            self._dirty = True

        logger.debug(f"Added {len(chunks)} chunks from doc {doc_id} to BM25 index (total: {len(self._corpus_texts)})")

    def remove_document(self, doc_id: str):
        """Remove all chunks for a document from the index.

        Args:
            doc_id: Document ID to remove.
        """
        with self._lock:
            # Filter out chunks belonging to this document
            filtered = [
                (text, meta)
                for text, meta in zip(self._corpus_texts, self._corpus_metadata)
                if meta.get("doc_id") != doc_id
            ]
            if filtered:
                self._corpus_texts, self._corpus_metadata = zip(*filtered)
                self._corpus_texts = list(self._corpus_texts)
                self._corpus_metadata = list(self._corpus_metadata)
            else:
                self._corpus_texts = []
                self._corpus_metadata = []
            self._dirty = True

    def _rebuild_index(self):
        """Rebuild the BM25 index from the current corpus."""
        if not _BM25S_AVAILABLE or not self._corpus_texts:
            self._retriever = None
            return

        # Tokenize corpus
        corpus_tokens = bm25s.tokenize(self._corpus_texts, stopwords="en")

        # Build retriever
        self._retriever = bm25s.BM25()
        self._retriever.index(corpus_tokens)
        self._dirty = False

        logger.info(f"BM25 index rebuilt with {len(self._corpus_texts)} documents")

    def search(
        self,
        query: str,
        top_k: int = 20,
        doc_ids: Optional[set] = None,
    ) -> List[Dict[str, Any]]:
        """Search the BM25 index.

        Args:
            query: Search query string.
            top_k: Number of results to return.
            doc_ids: Optional set of document IDs to filter results.

        Returns:
            List of result dicts with 'text', 'score', 'doc_id', 'metadata'.
        """
        if not _BM25S_AVAILABLE:
            return []

        with self._lock:
            if self._dirty:
                self._rebuild_index()

        if self._retriever is None or not self._corpus_texts:
            return []

        # Tokenize query
        query_tokens = bm25s.tokenize([query], stopwords="en")

        # Search
        results_obj, scores = self._retriever.retrieve(
            query_tokens, corpus=self._corpus_texts, k=min(top_k * 2, len(self._corpus_texts))
        )

        # Build result list
        results = []
        for idx_in_results in range(len(results_obj[0])):
            text = results_obj[0][idx_in_results]
            score = float(scores[0][idx_in_results])

            if score <= 0:
                continue

            # Find the metadata for this text by matching against corpus
            # bm25s returns the actual text, so find its index
            try:
                corpus_idx = self._corpus_texts.index(text)
                meta = self._corpus_metadata[corpus_idx]
            except (ValueError, IndexError):
                continue

            # Filter by document IDs if specified
            if doc_ids and meta.get("doc_id") not in doc_ids:
                continue

            results.append({
                "text": text,
                "score": score,
                "doc_id": meta.get("doc_id"),
                "metadata": meta.get("metadata", {}),
                "page_number": meta.get("page_number"),
                "match_type": "bm25",
            })

        return results[:top_k]

    @property
    def corpus_size(self) -> int:
        """Number of documents in the BM25 index."""
        return len(self._corpus_texts)


def rrf_fuse(
    *result_lists: List[Dict[str, Any]],
    k: int = 60,
) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion (RRF) to merge multiple ranked result lists.

    RRF(d) = SUM(1 / (k + rank_i(d))) across all lists where d appears.

    Args:
        *result_lists: Variable number of ranked result lists.
            Each result dict must have a 'text' key for deduplication.
        k: RRF constant (default 60, as per the original paper).

    Returns:
        Fused and sorted list of results with 'rrf_score' added.
    """
    # Score accumulator keyed by chunk text (or chunk_id if available)
    scores: Dict[str, float] = {}
    result_map: Dict[str, Dict[str, Any]] = {}

    for result_list in result_lists:
        for rank, result in enumerate(result_list):
            # Use chunk_id for dedup if available, otherwise text hash
            chunk_key = result.get("metadata", {}).get("chunk_id") or str(hash(result.get("text", "")))

            rrf_score = 1.0 / (k + rank + 1)
            scores[chunk_key] = scores.get(chunk_key, 0.0) + rrf_score

            # Keep the result with the best individual score
            if chunk_key not in result_map:
                result_map[chunk_key] = result.copy()
            else:
                # Merge match types
                existing_type = result_map[chunk_key].get("match_type", "")
                new_type = result.get("match_type", "")
                if new_type and new_type not in existing_type:
                    result_map[chunk_key]["match_type"] = f"{existing_type}+{new_type}"

    # Sort by fused RRF score
    fused = []
    for chunk_key in sorted(scores, key=scores.get, reverse=True):
        result = result_map[chunk_key]
        result["rrf_score"] = scores[chunk_key]
        result["relevance_score"] = scores[chunk_key]
        fused.append(result)

    return fused


def get_bm25_service() -> BM25IndexService:
    """Get the singleton BM25 index service."""
    return BM25IndexService.get_instance()
