"""
Atlas 3.0: Information Retrieval Expert.

Deep-dives into specific documents to gather evidence proving or disproving
a given hypothesis. Uses vector search, BM25, graph queries, and optionally
web search via DuckDuckGo.

Tools: read_document_section, web_search_duckduckgo, bm25_search, vector_search
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.services.llm import LLMService
from app.services.bm25_index import get_bm25_service
from app.core.config import settings
from app.core.database import get_session, Document

logger = logging.getLogger(__name__)


async def retrieval_search(
    state: dict,
    llm_service: LLMService,
    qdrant_client: Any,
    collection_name: str,
    graph_service: Any,
) -> dict:
    """Retrieve evidence for the current hypotheses/sub-tasks.

    Executes multi-modal retrieval:
    1. Vector similarity search (Qdrant)
    2. BM25 sparse keyword search
    3. Knowledge graph traversal
    4. Web search fallback (DuckDuckGo, if configured)

    Args:
        state: Current MoE state dict.
        llm_service: LLM service for embeddings and query expansion.
        qdrant_client: Qdrant client for vector search.
        collection_name: Qdrant collection name.
        graph_service: Graph service for knowledge graph queries.

    Returns:
        Updated state with 'retrieved_evidence' populated.
    """
    query = state["query"]
    project_id = state.get("project_id", "")
    sub_tasks = state.get("sub_tasks", [query])
    selected_hypothesis = state.get("selected_hypothesis", query)
    existing_evidence = state.get("retrieved_evidence", [])
    trace = state.get("reasoning_trace", [])
    current_round = state.get("current_round", 0)
    retrieval_queries = state.get("retrieval_queries", [])

    trace.append(f"[Retrieval Expert] Round {current_round + 1}: Searching for evidence...")

    # Determine search queries from sub-tasks and hypothesis
    search_queries = []
    if selected_hypothesis and selected_hypothesis != query:
        search_queries.append(selected_hypothesis)
    for task in sub_tasks[:3]:
        if task not in search_queries:
            search_queries.append(task)
    if query not in search_queries:
        search_queries.insert(0, query)

    # Get active document IDs
    session = get_session()
    try:
        doc_query = session.query(Document).filter(Document.status == "completed")
        if project_id:
            doc_query = doc_query.filter(Document.project_id == project_id)
        active_doc_ids = {str(doc.id) for doc in doc_query.all()}
    finally:
        session.close()

    if not active_doc_ids:
        trace.append("[Retrieval Expert] No active documents found")
        return {**state, "reasoning_trace": trace, "current_round": current_round + 1}

    all_evidence = list(existing_evidence)
    seen_texts = {e.get("text", "")[:100] for e in existing_evidence}

    for search_query in search_queries[:3]:
        retrieval_queries.append(search_query)

        # 1. Vector search
        try:
            query_embedding = await llm_service.embed(search_query)
            loop = asyncio.get_running_loop()

            def _search():
                return qdrant_client.query_points(
                    collection_name=collection_name,
                    query=query_embedding,
                    limit=10,
                ).points

            vector_results = await loop.run_in_executor(None, _search)

            for r in vector_results:
                if r.payload.get("doc_id") not in active_doc_ids:
                    continue
                text = r.payload.get("text", "")
                if text[:100] in seen_texts:
                    continue
                seen_texts.add(text[:100])
                meta = r.payload.get("metadata", {})
                all_evidence.append({
                    "text": text,
                    "source": meta.get("filename", "Unknown"),
                    "page": meta.get("page", 0),
                    "doc_id": r.payload.get("doc_id", ""),
                    "score": float(r.score),
                    "match_type": "vector",
                })
        except Exception as e:
            logger.debug(f"Vector search failed for '{search_query[:50]}': {e}")

        # 2. BM25 search
        try:
            bm25 = get_bm25_service()
            if bm25.is_available() and bm25.corpus_size > 0:
                bm25_results = bm25.search(search_query, top_k=10, doc_ids=active_doc_ids)
                for r in bm25_results:
                    text = r.get("text", "")
                    if text[:100] in seen_texts:
                        continue
                    seen_texts.add(text[:100])
                    meta = r.get("metadata", {})
                    all_evidence.append({
                        "text": text,
                        "source": meta.get("filename", "Unknown"),
                        "page": r.get("page_number", 0),
                        "doc_id": r.get("doc_id", ""),
                        "score": r.get("score", 0.5),
                        "match_type": "bm25",
                    })
        except Exception as e:
            logger.debug(f"BM25 search failed: {e}")

    # 3. Optional: DuckDuckGo web search fallback
    if len(all_evidence) < 3:
        web_results = await _web_search_fallback(query)
        for r in web_results:
            if r.get("text", "")[:100] not in seen_texts:
                seen_texts.add(r["text"][:100])
                all_evidence.append(r)

    # Sort by score and limit
    all_evidence.sort(key=lambda x: x.get("score", 0), reverse=True)
    all_evidence = all_evidence[:20]

    trace.append(f"[Retrieval Expert] Found {len(all_evidence)} evidence items total")

    return {
        **state,
        "retrieved_evidence": all_evidence,
        "retrieval_queries": retrieval_queries,
        "current_round": current_round + 1,
        "reasoning_trace": trace,
    }


async def _web_search_fallback(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Fallback web search using DuckDuckGo (free, no API key needed).

    Only used when local document evidence is insufficient.
    """
    results = []
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "text": r.get("body", ""),
                    "source": r.get("href", "web"),
                    "page": 0,
                    "doc_id": "",
                    "score": 0.3,
                    "match_type": "web",
                    "title": r.get("title", ""),
                })
    except ImportError:
        logger.debug("duckduckgo-search not installed, skipping web fallback")
    except Exception as e:
        logger.debug(f"Web search fallback failed: {e}")

    return results
