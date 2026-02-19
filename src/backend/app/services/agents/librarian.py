"""
Librarian Agent - Fast factual retrieval for simple queries.

Architecture:
  Retrieve (vector search) -> Answer (single LLM call) -> Cite (source attribution)

This agent handles ~80% of queries in <5 seconds vs Navigator's 30-60s.
"""

from typing import Any, Dict, List, TypedDict
from langgraph.graph import StateGraph, END
from app.core.config import settings
from app.services.rerank import get_rerank_service
import logging

logger = logging.getLogger(__name__)

class LibrarianState(TypedDict, total=False):
    query: str
    project_id: str
    brain: str
    chunks: List[Dict[str, Any]]
    answer: str
    citations: List[Dict[str, Any]]
    confidence_score: float
    reasoning_trace: List[str]
    status: str

def format_chunks(chunks: List[Dict[str, Any]], max_chunks: int = 5) -> str:
    """Format chunks with citations for LLM prompts."""
    if not chunks:
        return "[No evidence available]"

    formatted_parts = []
    for i, chunk in enumerate(chunks[:max_chunks], 1):
        metadata = chunk.get("metadata", {})
        filename = metadata.get("filename", "Unknown")
        page = metadata.get("page", "?")
        text = chunk.get("text", "")[:500]  # Limit to 500 chars per chunk

        formatted_parts.append(
            f"[Source {i}: {filename}, Page {page}]\n{text}"
        )

    return "\n\n".join(formatted_parts)

def _build_librarian_graph(
    llm_service,
    qdrant_client,
    collection_name: str,
) -> StateGraph:
    """Simple 2-node graph: Retrieve -> Answer."""

    async def retrieve_node(state: LibrarianState) -> LibrarianState:
        """Vector search + rerank, no graph exploration."""
        trace = ["Librarian: Searching document library..."]

        try:
            embedding = await llm_service.embed(state["query"])
            
            # NOTE: qdrant-client 1.12+ uses query_points
            results = qdrant_client.query_points(
                collection_name=collection_name,
                query=embedding,
                limit=8,
            ).points

            chunks = []
            for r in results:
                payload = r.payload or {}
                chunks.append({
                    "text": payload.get("text", ""),
                    "metadata": payload.get("metadata", {}),
                    "score": r.score,
                })

            # Optional: rerank
            if settings.ENABLE_RERANKING and chunks:
                try:
                    reranker = get_rerank_service()
                    chunks = await reranker.rerank(
                        query=state["query"],
                        documents=chunks,
                        top_n=5
                    )
                except Exception as e:
                    logger.warning(f"Reranking failed: {e}")
                    trace.append(f"Reranking failed: {e}")

            trace.append(f"Found {len(chunks)} relevant passages")
            return {**state, "chunks": chunks, "reasoning_trace": trace}
            
        except Exception as e:
            trace.append(f"Retrieval failed: {e}")
            return {**state, "chunks": [], "reasoning_trace": trace}

    async def answer_node(state: LibrarianState) -> LibrarianState:
        """Single LLM call with retrieved context."""
        trace = list(state.get("reasoning_trace", []))
        chunks = state.get("chunks", [])

        if not chunks:
            return {
                **state,
                "answer": "I couldn't find relevant information in your documents.",
                "citations": [],
                "confidence_score": 0.0,
                "status": "completed",
                "reasoning_trace": trace + ["No relevant chunks found"],
            }

        context = format_chunks(chunks, max_chunks=5)

        prompt = f"""Answer this question using ONLY the provided evidence.
Cite every fact as [Source: filename, Page: X].

Question: {state["query"]}

Evidence:
{context}

If the evidence doesn't contain the answer, say "I cannot find this in your documents."

Answer:"""

        try:
            answer = await llm_service.generate(
                prompt=prompt, temperature=0.1, max_tokens=1024
            )
        except Exception as e:
            answer = f"Error generating answer: {e}"

        citations = [
            {
                "source": c["metadata"].get("filename", "Unknown"),
                "page": c["metadata"].get("page", 1),
                "excerpt": c["text"][:200],
                "relevance": c.get("score", 0),
            }
            for c in chunks[:5]
        ]

        return {
            **state,
            "answer": answer.strip(),
            "citations": citations,
            "confidence_score": 0.7,  # Default for simple retrieval
            "status": "completed",
            "reasoning_trace": trace + ["Answer generated"],
        }

    graph = StateGraph(LibrarianState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    return graph
