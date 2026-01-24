"""
Chat Service - Interface to Ollama LLM for chat functionality.
"""
from typing import Dict, Any
import ollama

from app.core.config import settings
from app.services.retrieval import RetrievalService


class ChatService:
    """Handles chat interactions with the LLM."""
    
    def __init__(self):
        self.retrieval_service = RetrievalService()
    
    def chat(self, user_question: str) -> Dict[str, Any]:
        """
        Process a chat query using hybrid RAG retrieval.
        
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
        # Use retrieval service to get answer
        result = self.retrieval_service.query_atlas(user_question)
        
        # Format citations from vector chunks
        citations = []
        for chunk in result["context"]["vector_chunks"][:5]:
            metadata = chunk.get("metadata", {})
            citations.append({
                "source": metadata.get("filename", "Unknown"),
                "doc_id": chunk.get("doc_id"),
                "page": metadata.get("page"),
                "excerpt": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"]
            })
        
        # Format relationships from graph edges
        relationships = []
        for edge in result["context"]["graph_edges"][:10]:
            relationships.append({
                "source_id": edge["source_id"],
                "target_id": edge["target_id"],
                "type": edge["type"],
                "properties": edge["properties"]
            })
        
        return {
            "answer": result["answer"],
            "reasoning": f"Retrieved {len(result['context']['vector_chunks'])} text chunks and {len(result['context']['graph_nodes'])} graph nodes",
            "citations": citations,
            "relationships": relationships,
            "context_sources": {
                "vector_chunks": len(result["context"]["vector_chunks"]),
                "graph_nodes": len(result["context"]["graph_nodes"]),
                "graph_edges": len(result["context"]["graph_edges"])
            }
        }
