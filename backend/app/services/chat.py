"""
Chat Service - Interface for chat functionality using bundled LLM.

Production Desktop App: Uses bundled llama-cpp-python via RetrievalService.
"""
from typing import Dict, Any

from app.services.retrieval import RetrievalService


class ChatService:
    """Handles chat interactions with the LLM."""
    
    def __init__(self):
        self.retrieval_service = RetrievalService()
    
    async def chat(self, user_question: str) -> Dict[str, Any]:
        """
        Process a chat query using hybrid RAG retrieval (async, GPU-bound).
        
        Args:
            user_question: The user's question
            
        Returns:
            {
                "answer": str,
                "reasoning": str,
                "citations": List[Dict],
                "relationships": List[Dict],
                "context_sources": Dict
            }
        """
        # Use retrieval service to get answer (async, GPU-bound)
        result = await self.retrieval_service.query_atlas(user_question)
        context = result.get("context") or {
            "vector_chunks": [],
            "graph_nodes": [],
            "graph_edges": [],
        }
        vector_chunks = context.get("vector_chunks", [])
        graph_edges = context.get("graph_edges", [])
        graph_nodes = context.get("graph_nodes", [])

        # Format citations from vector chunks (include doc_id for PDF opening)
        citations = []
        for chunk in vector_chunks[:5]:
            metadata = chunk.get("metadata", {})
            page = metadata.get("page")
            citations.append({
                "source": metadata.get("filename", "Unknown"),
                "doc_id": chunk.get("doc_id"),
                "page": page if page is not None else 1,
                "excerpt": (chunk.get("text") or "")[:200] + ("..." if len(chunk.get("text", "")) > 200 else ""),
            })

        # Format relationships from graph edges
        relationships = []
        for edge in graph_edges[:10]:
            relationships.append({
                "source_id": edge.get("source_id", ""),
                "target_id": edge.get("target_id", ""),
                "type": edge.get("type", ""),
                "properties": edge.get("properties", {}),
            })

        # User-friendly answer when retrieval returned empty or failed
        answer = result.get("answer") or ""
        status = result.get("status")
        if not answer and status in ("no_results", "no_documents", "extraction_failed", "generation_failed"):
            err = result.get("error", {})
            msg = err.get("message", "Something went wrong.")
            answer = (
                "I couldn't find an answer from your documents. "
                f"{msg} Try rephrasing your question or adding more relevant documents."
            )

        return {
            "answer": answer,
            "reasoning": f"Retrieved {len(vector_chunks)} text chunks and {len(graph_nodes)} graph nodes",
            "citations": citations,
            "relationships": relationships,
            "context_sources": {
                "vector_chunks": len(vector_chunks),
                "graph_nodes": len(graph_nodes),
                "graph_edges": len(graph_edges),
            },
        }
