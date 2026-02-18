"""RAPTOR-lite: Recursive Abstractive Processing for Tree-Organized Retrieval.

Builds a 3-level hierarchy over document chunks:
  L0: Raw chunks (leaf nodes)
  L1: Cluster summaries (grouped by semantic similarity)
  L2: Document-level summary (root node)

This lets retrieval match at the right granularity:
  - Detail questions hit L0 chunks
  - Overview questions hit L1/L2 summaries
"""
import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.info("scikit-learn not installed - RAPTOR hierarchy disabled")


class RaptorService:
    """Build hierarchical summaries over document chunks."""

    def __init__(self, llm_service):
        """
        Args:
            llm_service: LLMService instance for generating summaries and embeddings
        """
        self.llm = llm_service

    async def build_hierarchy(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        doc_id: str,
        filename: str,
        n_clusters: int = 5
    ) -> Dict[str, Any]:
        """Build RAPTOR tree from chunks and their embeddings.

        Args:
            chunks: L0 chunks from ingestion
            embeddings: Corresponding embedding vectors
            doc_id: Document ID
            filename: Source filename
            n_clusters: Number of L1 cluster summaries to generate

        Returns:
            Dict with L1 (cluster summaries) and L2 (document summary),
            each with text and embedding ready for Qdrant upsert
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, skipping RAPTOR hierarchy")
            return {"L1": [], "L2": None}

        if len(chunks) < 3:
            logger.info("Too few chunks for RAPTOR clustering, skipping")
            return {"L1": [], "L2": None}

        # Adjust cluster count to avoid more clusters than chunks
        actual_clusters = min(n_clusters, max(1, len(chunks) // 3))

        # Level 1: Cluster and summarize
        L1 = await self._build_cluster_summaries(
            chunks, embeddings, actual_clusters, doc_id, filename
        )

        # Level 2: Global document summary from L1 summaries
        L2 = await self._build_global_summary(L1, doc_id, filename)

        logger.info(
            f"RAPTOR hierarchy: {len(chunks)} L0 chunks -> "
            f"{len(L1)} L1 summaries -> 1 L2 summary"
        )
        return {"L1": L1, "L2": L2}

    async def _build_cluster_summaries(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        n_clusters: int,
        doc_id: str,
        filename: str,
    ) -> List[Dict[str, Any]]:
        """Cluster chunks by embedding similarity, then summarize each cluster."""
        X = np.array(embeddings)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)

        summaries = []
        for cluster_id in range(n_clusters):
            cluster_indices = [i for i in range(len(chunks)) if labels[i] == cluster_id]
            if not cluster_indices:
                continue

            cluster_chunks = [chunks[i] for i in cluster_indices]

            # Concatenate chunk texts (cap at ~4000 chars to avoid token overflow)
            combined_text = "\n\n".join([c["text"] for c in cluster_chunks])
            if len(combined_text) > 4000:
                combined_text = combined_text[:4000] + "..."

            # Generate summary
            prompt = (
                f"Summarize the following text cluster concisely (2-3 sentences). "
                f"Focus on the key concepts, findings, and relationships.\n\n"
                f"Text:\n{combined_text}\n\n"
                f"Summary:"
            )

            try:
                summary_text = await self.llm.generate(
                    prompt=prompt, temperature=0.2, max_tokens=256
                )
                summary_text = summary_text.strip()
            except Exception as e:
                logger.warning(f"Cluster {cluster_id} summary generation failed: {e}")
                # Fallback: use first 200 chars of combined text
                summary_text = combined_text[:200] + "..."

            # Embed the summary
            try:
                summary_embedding = await self.llm.embed(summary_text)
            except Exception as e:
                logger.warning(f"Cluster {cluster_id} summary embedding failed: {e}")
                # Use centroid of cluster embeddings as fallback
                cluster_embeddings = [embeddings[i] for i in cluster_indices]
                summary_embedding = np.mean(cluster_embeddings, axis=0).tolist()

            summaries.append({
                "text": summary_text,
                "embedding": summary_embedding,
                "cluster_id": cluster_id,
                "child_chunk_indices": cluster_indices,
                "metadata": {
                    "filename": filename,
                    "doc_id": doc_id,
                    "chunk_type": "cluster_summary",
                    "hierarchy_level": 1,
                    "n_children": len(cluster_indices),
                }
            })

        return summaries

    async def _build_global_summary(
        self,
        cluster_summaries: List[Dict[str, Any]],
        doc_id: str,
        filename: str,
    ) -> Optional[Dict[str, Any]]:
        """Generate a document-level summary from cluster summaries."""
        if not cluster_summaries:
            return None

        combined = "\n\n".join([
            f"Section {i+1}: {s['text']}"
            for i, s in enumerate(cluster_summaries)
        ])

        prompt = (
            f"Create a comprehensive document summary (3-5 sentences) based on "
            f"these section summaries:\n\n{combined}\n\n"
            f"Document Summary:"
        )

        try:
            summary_text = await self.llm.generate(
                prompt=prompt, temperature=0.2, max_tokens=512
            )
            summary_text = summary_text.strip()
        except Exception as e:
            logger.warning(f"Global summary generation failed: {e}")
            summary_text = " ".join([s["text"][:100] for s in cluster_summaries])

        try:
            summary_embedding = await self.llm.embed(summary_text)
        except Exception as e:
            logger.warning(f"Global summary embedding failed: {e}")
            # Average of L1 embeddings as fallback
            all_embs = [s["embedding"] for s in cluster_summaries if s.get("embedding")]
            summary_embedding = np.mean(all_embs, axis=0).tolist() if all_embs else []

        return {
            "text": summary_text,
            "embedding": summary_embedding,
            "metadata": {
                "filename": filename,
                "doc_id": doc_id,
                "chunk_type": "document_summary",
                "hierarchy_level": 2,
                "n_children": len(cluster_summaries),
            }
        }

    @classmethod
    def is_available(cls) -> bool:
        return SKLEARN_AVAILABLE
