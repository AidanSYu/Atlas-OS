"""
Vector Store Module - Qdrant integration for semantic search.

This module handles:
1. Document chunk embeddings storage
2. Similarity search
3. Metadata filtering
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import math
import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from config import settings

class VectorStore:
    """Manages vector embeddings with pluggable backends (Qdrant or local JSON)."""
    
    def __init__(self):
        self.backend = settings.VECTOR_BACKEND.lower()
        if self.backend == "qdrant":
            self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
            self.collection_name = settings.QDRANT_COLLECTION
            self._ensure_collection()
        else:
            self.local_path = Path(settings.LOCAL_VECTOR_PATH)
            self.local_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.local_path.exists():
                self.local_path.write_text(json.dumps([]))
    
    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            # Get embedding dimension from Ollama
            test_embedding = self._embed_text("test")
            dimension = len(test_embedding)
            
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE
                )
            )
    
    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using Ollama."""
        response = ollama.embeddings(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            prompt=text
        )
        return response['embedding']

    def _load_local_records(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.local_path.read_text())
        except Exception:
            return []

    def _save_local_records(self, records: List[Dict[str, Any]]):
        self.local_path.write_text(json.dumps(records))

    def _cosine(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    
    def add_chunks(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Add document chunks to the configured vector backend."""
        if self.backend == "qdrant":
            points = []
            for chunk in chunks:
                embedding = self._embed_text(chunk["text"])
                point = PointStruct(
                    id=chunk["chunk_id"],
                    vector=embedding,
                    payload={
                        "doc_id": chunk["doc_id"],
                        "text": chunk["text"],
                        "metadata": chunk.get("metadata", {})
                    }
                )
                points.append(point)
            self.client.upsert(collection_name=self.collection_name, points=points)
            return [chunk["chunk_id"] for chunk in chunks]
        else:
            records = self._load_local_records()
            for chunk in chunks:
                embedding = self._embed_text(chunk["text"])
                records.append({
                    "chunk_id": chunk["chunk_id"],
                    "doc_id": chunk["doc_id"],
                    "text": chunk["text"],
                    "metadata": chunk.get("metadata", {}),
                    "embedding": embedding
                })
            self._save_local_records(records)
            return [chunk["chunk_id"] for chunk in chunks]
    
    def search(
        self, 
        query: str, 
        top_k: int = 5,
        doc_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over document chunks.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            doc_id: Optional document ID to filter by
            filters: Optional metadata filters
        
        Returns:
            List of results with text, metadata, and relevance score
        """
        query_embedding = self._embed_text(query)
        
        if self.backend == "qdrant":
            query_filter = None
            if doc_id or filters:
                conditions = []
                if doc_id:
                    conditions.append(FieldCondition(key="doc_id", match=MatchValue(value=doc_id)))
                if filters:
                    for key, value in filters.items():
                        conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value)))
                if conditions:
                    query_filter = Filter(must=conditions)

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=query_filter
            )
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "chunk_id": result.id,
                    "text": result.payload["text"],
                    "doc_id": result.payload["doc_id"],
                    "metadata": result.payload.get("metadata", {}),
                    "relevance_score": result.score
                })
            return formatted_results
        else:
            records = self._load_local_records()
            scored = []
            for rec in records:
                if doc_id and rec.get("doc_id") != doc_id:
                    continue
                if filters:
                    match = True
                    for k, v in filters.items():
                        if rec.get("metadata", {}).get(k) != v:
                            match = False
                            break
                    if not match:
                        continue
                score = self._cosine(query_embedding, rec.get("embedding", []))
                scored.append((score, rec))
            scored.sort(key=lambda x: x[0], reverse=True)
            top = scored[:top_k]
            return [
                {
                    "chunk_id": rec["chunk_id"],
                    "text": rec["text"],
                    "doc_id": rec["doc_id"],
                    "metadata": rec.get("metadata", {}),
                    "relevance_score": score
                }
                for score, rec in top
            ]
    
    def delete_document(self, doc_id: str):
        """Delete all chunks for a document."""
        if self.backend == "qdrant":
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                )
            )
        else:
            records = self._load_local_records()
            filtered = [r for r in records if r.get("doc_id") != doc_id]
            self._save_local_records(filtered)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        if self.backend == "qdrant":
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "backend": "qdrant",
                "total_vectors": collection_info.points_count,
                "vector_dimension": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.name
            }
        else:
            records = self._load_local_records()
            return {
                "backend": "local",
                "total_vectors": len(records),
                "store_path": str(self.local_path)
            }
