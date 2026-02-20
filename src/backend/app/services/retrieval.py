"""
Retrieval Service - Hybrid RAG retrieval logic.

Implements hybrid search combining:
1. Vector search (semantic similarity via embedded Qdrant)
2. Entity-based matching (knowledge graph nodes)
3. Exact text matching (dates, numbers, specific phrases)
4. Graph expansion (1-hop neighborhood)
5. Document filtering (only active/completed documents)

Production Desktop Sidecar: SQLite + embedded Qdrant + bundled LLMs.
"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func
import json
import logging
import asyncio

from app.core.database import get_session, Node, Edge, Document
from app.core.config import settings
from app.services.llm import LLMService
from app.core.qdrant_store import get_qdrant_client
from app.services.rerank import get_rerank_service
from qdrant_client.models import Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)


class RetrievalService:
    """Handles hybrid retrieval from vector store and knowledge graph."""

    def __init__(self):
        self.llm_service = LLMService.get_instance()
        # Embedded Qdrant - shared singleton
        self.qdrant_client = get_qdrant_client()
        self.collection_name = settings.QDRANT_COLLECTION
        self.reranker = get_rerank_service()
        logger.info("RetrievalService initialized (embedded Qdrant)")

    async def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using bundled LLM service."""
        return await self.llm_service.embed(text)

    async def _extract_query_entities(self, query: str) -> Dict[str, Any]:
        """Extract entities, dates, and key terms from query using LLM."""
        prompt = f"""Extract key information from this query. Focus on:
- Entities: people, places, organizations, concepts
- Dates and time periods
- Specific numbers, measurements, or values
- Key phrases that should be matched exactly

Query: {query}

Return ONLY a JSON object with:
{{
  "entities": ["entity1", "entity2"],
  "dates": ["1920", "1930"],
  "date_ranges": [{{"start": "1920", "end": "1930"}}],
  "key_phrases": ["exact phrase to match"]
}}

If no dates/entities found, return empty arrays."""

        try:
            response_text = await self.llm_service.generate(
                prompt=prompt, temperature=0.1, max_tokens=512
            )
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
        except Exception as e:
            logger.debug(f"Entity extraction failed: {e}")

        return {"entities": [], "dates": [], "date_ranges": [], "key_phrases": []}

    async def _get_active_document_ids(self, session: Session) -> Set[str]:
        """Get set of active (completed) document IDs."""
        active_docs = session.query(Document).filter(Document.status == "completed").all()
        return {str(doc.id) for doc in active_docs}

    async def query_atlas(
        self, user_question: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main retrieval function - implements hybrid RAG workflow.

        Args:
            user_question: The query string
            project_id: Optional project scope

        Returns:
            Dict with answer, context (vector_chunks, graph_nodes, graph_edges)
        """
        session = get_session()
        try:
            # Step 0: Extract entities/dates from query
            query_info = await self._extract_query_entities(user_question)
            # Use .get() with defaults to handle malformed LLM output
            entities = query_info.get('entities', [])
            dates = query_info.get('dates', [])
            logger.info(
                f"Extracted from query: entities={entities}, dates={dates}"
            )

            # Step 0.5: Get active document IDs (optionally scoped to project)
            doc_query = session.query(Document).filter(Document.status == "completed")
            if project_id:
                doc_query = doc_query.filter(Document.project_id == project_id)
            active_docs = doc_query.all()
            active_doc_ids = {str(doc.id) for doc in active_docs}

            if not active_doc_ids:
                return {
                    "status": "no_documents",
                    "answer": "",
                    "context": {"vector_chunks": [], "graph_nodes": [], "graph_edges": []},
                }

            # Step 1: Vector Search
            query_embedding = await self._embed_text(user_question)
            loop = asyncio.get_running_loop()

            def _qdrant_search():
                return self.qdrant_client.query_points(
                    collection_name=self.collection_name,
                    query=query_embedding,
                    limit=20,
                ).points

            vector_results = await loop.run_in_executor(None, _qdrant_search)
            vector_results = [
                r for r in vector_results if r.payload.get("doc_id") in active_doc_ids
            ]

            if not vector_results:
                return {
                    "status": "no_results",
                    "answer": "",
                    "context": {"vector_chunks": [], "graph_nodes": [], "graph_edges": []},
                }

            # Step 2: Entity-based matching
            entity_matched_chunks = []
            if entities:
                for entity_name in entities:
                    # SQLite JSON: use json_extract for property queries
                    node_query = session.query(Node).join(
                        Document, Node.document_id == Document.id
                    ).filter(Document.status == "completed")
                    if project_id:
                        node_query = node_query.filter(Node.project_id == project_id)

                    # Task 0.2: Fix Entity Matching Performance
                    # Use SQLite json_extract for SQL-level filtering (no Python loop)
                    # This replaces the old logic that loaded 100+ nodes into memory
                    matching_nodes = node_query.filter(
                        func.lower(
                            func.json_extract(Node.properties, '$.name')
                        ).contains(entity_name.lower())
                    ).limit(20).all()

                    seen_chunk_ids = set()
                    for node in matching_nodes:
                        chunk_id = (node.properties or {}).get("chunk_id")
                        if chunk_id and chunk_id not in seen_chunk_ids:
                            seen_chunk_ids.add(chunk_id)
                            try:
                                chunk_result = await loop.run_in_executor(
                                    None,
                                    lambda cid=chunk_id: self.qdrant_client.retrieve(
                                        collection_name=self.collection_name, ids=[cid]
                                    ),
                                )
                                if chunk_result and chunk_result[0].payload.get("doc_id") in active_doc_ids:
                                    payload = chunk_result[0].payload
                                    entity_matched_chunks.append(
                                        {
                                            "text": payload.get("text", ""),
                                            "doc_id": payload.get("doc_id"),
                                            "metadata": {**payload.get("metadata", {}), "chunk_id": chunk_id},
                                            "relevance_score": 0.95,
                                            "match_type": "entity",
                                        }
                                    )
                            except Exception as e:
                                logger.debug(f"Error retrieving chunk {chunk_id}: {e}")

            # Step 3: Exact text matching for dates/key phrases
            exact_matched_chunks = []
            key_phrases = query_info.get('key_phrases', [])
            search_terms = dates + key_phrases
            if search_terms:
                seen_exact_chunks: set = set()
                for doc_id in list(active_doc_ids)[:5]:
                    try:
                        doc_filter = Filter(
                            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                        )
                        scroll_result = await loop.run_in_executor(
                            None,
                            lambda: self.qdrant_client.scroll(
                                collection_name=self.collection_name,
                                scroll_filter=doc_filter,
                                limit=200,
                            ),
                        )
                        points, _ = scroll_result
                        for point in points:
                            chunk_id = point.id
                            if chunk_id in seen_exact_chunks:
                                continue
                            text = point.payload.get("text", "").lower()
                            for term in search_terms:
                                if term.lower() in text:
                                    seen_exact_chunks.add(chunk_id)
                                    exact_matched_chunks.append(
                                        {
                                            "text": point.payload.get("text", ""),
                                            "doc_id": point.payload.get("doc_id"),
                                            "metadata": {**point.payload.get("metadata", {}), "chunk_id": str(chunk_id)},
                                            "relevance_score": 0.98,
                                            "match_type": "exact",
                                            "matched_term": term,
                                        }
                                    )
                                    break
                    except Exception as e:
                        logger.debug(f"Error searching document {doc_id}: {e}")

            # Step 4: Combine and deduplicate chunks
            all_chunks: Dict[str, Dict] = {}

            for result in vector_results[:10]:
                payload = result.payload
                chunk_id = str(result.id)
                if chunk_id not in all_chunks:
                    all_chunks[chunk_id] = {
                        "text": payload.get("text", ""),
                        "doc_id": payload.get("doc_id"),
                        "metadata": {**payload.get("metadata", {}), "chunk_id": chunk_id},
                        "relevance_score": float(result.score),
                        "match_type": "vector",
                    }

            for chunk in entity_matched_chunks:
                chunk_id = chunk.get("metadata", {}).get("chunk_id", "")
                if chunk_id and chunk_id not in all_chunks:
                    all_chunks[chunk_id] = chunk
                elif chunk_id in all_chunks:
                    all_chunks[chunk_id]["relevance_score"] = max(
                        all_chunks[chunk_id]["relevance_score"], 0.95
                    )

            for chunk in exact_matched_chunks:
                chunk_id = chunk.get("metadata", {}).get("chunk_id", "")
                if chunk_id and chunk_id not in all_chunks:
                    all_chunks[chunk_id] = chunk
                elif chunk_id in all_chunks:
                    all_chunks[chunk_id]["relevance_score"] = max(
                        all_chunks[chunk_id]["relevance_score"], 0.98
                    )

            candidate_chunks = sorted(all_chunks.values(), key=lambda x: x["relevance_score"], reverse=True)[:20]

            # Step 4.5: Reranking (Phase B1) - Cross-encoder precision scoring
            if settings.ENABLE_RERANKING and len(candidate_chunks) > 0:
                try:
                    vector_chunks = await self.reranker.rerank(
                        query=user_question,
                        documents=candidate_chunks,
                        top_n=settings.RERANK_TOP_N,
                    )
                    logger.info(f"Reranked {len(candidate_chunks)} chunks -> top {len(vector_chunks)}")
                except Exception as e:
                    logger.warning(f"Reranking failed, using original ordering: {e}")
                    vector_chunks = candidate_chunks[:10]
            else:
                vector_chunks = candidate_chunks[:10]

            # Step 5: Graph Expansion - 1-hop neighborhood
            node_ids_from_chunks: set = set()
            for chunk in vector_chunks:
                metadata = chunk.get("metadata", {})
                if "node_ids" in metadata:
                    node_ids = metadata["node_ids"]
                    if isinstance(node_ids, str):
                        node_ids = [nid.strip() for nid in node_ids.split(",") if nid.strip()]
                    if isinstance(node_ids, list):
                        node_ids_from_chunks.update(node_ids)
                chunk_id = metadata.get("chunk_id")
                if chunk_id:
                    try:
                        nodes = session.query(Node).filter(
                            Node.properties.like(f'%"chunk_id": "{chunk_id}"%')
                        ).all()
                        # Fallback: filter in Python for JSON
                        if not nodes:
                            all_nodes = session.query(Node).limit(500).all()
                            nodes = [
                                n for n in all_nodes
                                if (n.properties or {}).get("chunk_id") == chunk_id
                            ]
                        for node in nodes:
                            node_ids_from_chunks.add(str(node.id))
                    except Exception:
                        pass

            graph_nodes = []
            graph_edges = []

            if node_ids_from_chunks:
                node_id_list = list(node_ids_from_chunks)
                nodes = (
                    session.query(Node)
                    .options(
                        joinedload(Node.outgoing_edges).joinedload(Edge.target_node),
                        joinedload(Node.incoming_edges).joinedload(Edge.source_node),
                    )
                    .filter(Node.id.in_(node_id_list))
                    .all()
                )

                for node in nodes:
                    graph_nodes.append(
                        {"id": str(node.id), "label": node.label, "properties": node.properties}
                    )

                edges = (
                    session.query(Edge)
                    .options(joinedload(Edge.source_node), joinedload(Edge.target_node))
                    .filter(or_(Edge.source_id.in_(node_id_list), Edge.target_id.in_(node_id_list)))
                    .all()
                )

                connected_node_ids = set()
                for edge in edges:
                    graph_edges.append(
                        {
                            "id": str(edge.id),
                            "source_id": str(edge.source_id),
                            "target_id": str(edge.target_id),
                            "type": edge.type,
                            "properties": edge.properties,
                        }
                    )
                    connected_node_ids.add(edge.source_id)
                    connected_node_ids.add(edge.target_id)

                if connected_node_ids:
                    connected_nodes = (
                        session.query(Node).filter(Node.id.in_(list(connected_node_ids))).all()
                    )
                    for node in connected_nodes:
                        if str(node.id) not in [n["id"] for n in graph_nodes]:
                            graph_nodes.append(
                                {"id": str(node.id), "label": node.label, "properties": node.properties}
                            )

            # Step 6: Build context string for LLM
            context_parts = []
            context_parts.append("=" * 70)
            context_parts.append("RELEVANT TEXT CHUNKS FROM DOCUMENTS")
            context_parts.append("=" * 70)
            for i, chunk in enumerate(vector_chunks, 1):
                match_types = chunk.get("match_type", "vector")
                if isinstance(match_types, list):
                    match_types = ", ".join(match_types)
                context_parts.append(
                    f"\n[Chunk {i}] (Match: {match_types}, Score: {chunk['relevance_score']:.3f})"
                )
                context_parts.append(f"Source: {chunk['metadata'].get('filename', 'Unknown')}")
                if chunk["metadata"].get("page"):
                    context_parts.append(f"Page: {chunk['metadata']['page']}")
                context_parts.append(f"Full Text: {chunk['text']}")

            if graph_nodes:
                context_parts.append("\n" + "=" * 70)
                context_parts.append("RELATED CONCEPTS FROM KNOWLEDGE GRAPH")
                context_parts.append("=" * 70)
                for node in graph_nodes[:10]:
                    props = node["properties"]
                    name = props.get("name", "Unknown")
                    description = props.get("description", "")
                    context_parts.append(f"\n* {name} ({node['label']})")
                    if description:
                        context_parts.append(f"  Description: {description[:200]}")

            if graph_edges:
                context_parts.append("\n" + "=" * 70)
                context_parts.append("KEY RELATIONSHIPS")
                context_parts.append("=" * 70)
                for edge in graph_edges[:10]:
                    source_node = next((n for n in graph_nodes if n["id"] == edge["source_id"]), None)
                    target_node = next((n for n in graph_nodes if n["id"] == edge["target_id"]), None)
                    source_name = source_node["properties"].get("name", "Unknown") if source_node else "Unknown"
                    target_name = target_node["properties"].get("name", "Unknown") if target_node else "Unknown"
                    context_parts.append(f"-> {source_name} --[{edge['type']}]--> {target_name}")

            context_str = "\n".join(context_parts)

            # Step 7: Generate answer using LLM
            system_msg = (
                "You are a precise research librarian. Answer the user's question based primarily "
                "on the provided context. If you cannot find the answer, say "
                "\"I cannot find this information in the available documents.\""
            )

            user_msg = f"""QUESTION: {user_question}

CONTEXT:
{context_str}

CRITICAL INSTRUCTIONS:
1. Base your answer primarily on the context provided.
2. Cite the source document name and page number for EVERY fact.
3. Use this exact citation format: [Source: filename.pdf, Page: X]
4. Consolidate citations when multiple sentences come from the same page."""

            try:
                answer = await self.llm_service.generate_chat(
                    system_message=system_msg,
                    user_message=user_msg,
                    temperature=0.1,
                    max_tokens=2048,
                )
                return {
                    "status": "success",
                    "answer": answer,
                    "context": {
                        "vector_chunks": vector_chunks,
                        "graph_nodes": graph_nodes,
                        "graph_edges": graph_edges,
                    },
                }
            except Exception as e:
                logger.error(f"LLM generation failed: {e}", exc_info=True)
                return {
                    "status": "generation_failed",
                    "answer": "",
                    "context": {
                        "vector_chunks": vector_chunks,
                        "graph_nodes": graph_nodes,
                        "graph_edges": graph_edges,
                    },
                }
        finally:
            session.close()
