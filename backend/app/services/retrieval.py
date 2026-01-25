"""
Retrieval Service - Hybrid RAG retrieval logic with LLM-based NER.

Implements hybrid search combining:
1. Vector search (semantic similarity)
2. Entity-based matching (LLM-extracted entities from query)
3. Exact text matching (for dates, numbers, specific phrases)
4. Document filtering (only active documents)
"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import re
import json
import logging

from app.core.database import get_session, Node, Edge, Document
from app.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from ollama import AsyncClient

logger = logging.getLogger(__name__)


class RetrievalService:
    """Handles hybrid retrieval from vector store and knowledge graph."""
    
    def __init__(self):
        # Initialize Ollama async client for GPU-bound operations
        self.ollama_client = AsyncClient(host=settings.OLLAMA_BASE_URL)
        self.qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.collection_name = settings.QDRANT_COLLECTION
    
    async def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using Ollama (async, GPU-bound)."""
        response = await self.ollama_client.embeddings(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            prompt=text
        )
        return response['embedding']
    
    async def _extract_query_entities(self, query: str) -> Dict[str, Any]:
        """Extract entities, dates, and key terms from query using LLM."""
        prompt = f"""Extract key information from this query. Focus on:
- Entities: people, places, organizations, concepts
- Dates and time periods (e.g., "1920", "between 1920 and 1930", "1930s")
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

If no dates/entities found, return empty arrays.
Example: {{"entities": ["China"], "dates": ["1920", "1930"], "date_ranges": [{{"start": "1920", "end": "1930"}}], "key_phrases": []}}
"""
        try:
            response = await self.ollama_client.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                options={"temperature": 0.1}
            )
            response_text = response['response'].strip()
            
            # Extract JSON
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
        except Exception as e:
            logger.debug(f"Entity extraction failed: {e}")
        
        return {"entities": [], "dates": [], "date_ranges": [], "key_phrases": []}
    
    async def _get_active_document_ids(self, session: Session) -> Set[str]:
        """Get set of active (non-deleted) document IDs."""
        active_docs = session.query(Document).filter(
            Document.status == "completed"
        ).all()
        return {str(doc.id) for doc in active_docs}
    
    async def query_atlas(self, user_question: str) -> Dict[str, Any]:
        """
        Main retrieval function - implements hybrid RAG workflow with entity matching.
        
        Workflow:
        1. Extract entities/dates from query using LLM
        2. Get active document IDs (filter deleted docs)
        3. Vector Search: Query Qdrant for top chunks (filtered by active docs)
        4. Entity Matching: Find chunks containing query entities
        5. Exact Text Matching: Find chunks with dates/key phrases
        6. Graph Expansion: Extract node_ids, query 1-hop neighborhood
        7. Synthesis: Format context with exact quotes
        8. Generation: Send to Ollama with strict citation requirements
        
        Returns:
            {
                "answer": str,
                "context": {
                    "vector_chunks": List[Dict],
                    "graph_nodes": List[Dict],
                    "graph_edges": List[Dict]
                }
            }
        """
        session = get_session()
        try:
            # Step 0: Extract entities and dates from query
            query_info = await self._extract_query_entities(user_question)
            logger.info(f"Extracted from query: entities={query_info['entities']}, dates={query_info['dates']}, ranges={query_info['date_ranges']}")
            
            # Step 0.5: Get active document IDs
            active_doc_ids = await self._get_active_document_ids(session)
            if not active_doc_ids:
                return {
                    "answer": "No documents are available in the knowledge base.",
                    "context": {
                        "vector_chunks": [],
                        "graph_nodes": [],
                        "graph_edges": []
                    }
                }
            
            # Step 1: Vector Search - Get top chunks from Qdrant (filtered by active docs)
            query_embedding = await self._embed_text(user_question)
            
            # Filter to only active documents
            doc_filter = Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=list(active_doc_ids)[0]) if len(active_doc_ids) == 1 
                        else None  # Qdrant doesn't support OR easily, so we'll filter in Python
                    )
                ]
            ) if len(active_doc_ids) == 1 else None
            
            # Get more results initially, then filter
            vector_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=20,  # Get more, filter down
                query_filter=doc_filter
            )
            
            # Filter to only active documents
            vector_results = [r for r in vector_results if r.payload.get("doc_id") in active_doc_ids]
            
            if not vector_results:
                return {
                    "answer": "No relevant documents found to answer this query.",
                    "context": {
                        "vector_chunks": [],
                        "graph_nodes": [],
                        "graph_edges": []
                    }
                }
            
            # Step 2: Entity-based matching - Find chunks with matching entities
            entity_matched_chunks = []
            if query_info["entities"]:
                # Find nodes matching query entities (case-insensitive)
                entity_nodes = []
                for entity_name in query_info["entities"]:
                    # Query for nodes with matching name (case-insensitive)
                    # Use .in_() operator for efficient filtering by active document IDs
                    nodes = session.query(Node).filter(
                        and_(
                            Node.properties['name'].astext.ilike(f"%{entity_name}%"),
                            Node.properties['document_id'].astext.in_(list(active_doc_ids))
                        )
                    ).limit(20).all()
                    entity_nodes.extend(nodes)
                
                # Get chunks containing these entities
                seen_chunk_ids = set()
                for node in entity_nodes:
                    chunk_id = node.properties.get("chunk_id")
                    if chunk_id and chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_id)
                        # Search Qdrant for this chunk
                        try:
                            chunk_result = self.qdrant_client.retrieve(
                                collection_name=self.collection_name,
                                ids=[chunk_id]
                            )
                            if chunk_result and chunk_result[0].payload.get("doc_id") in active_doc_ids:
                                payload = chunk_result[0].payload
                                entity_matched_chunks.append({
                                    "text": payload.get("text", ""),
                                    "doc_id": payload.get("doc_id"),
                                    "metadata": {**payload.get("metadata", {}), "chunk_id": chunk_id},
                                    "relevance_score": 0.95,  # High score for entity match
                                    "match_type": "entity"
                                })
                        except Exception as e:
                            logger.debug(f"Error retrieving chunk {chunk_id}: {e}")
            
            # Step 3: Exact text matching for dates and key phrases
            exact_matched_chunks = []
            search_terms = query_info["dates"] + query_info["key_phrases"]
            if search_terms:
                # Search all active document chunks for exact matches
                seen_exact_chunks = set()
                for doc_id in list(active_doc_ids)[:5]:  # Limit to 5 docs for performance
                    try:
                        # Use scroll to get all chunks for this document
                        doc_filter = Filter(
                            must=[
                                FieldCondition(
                                    key="doc_id",
                                    match=MatchValue(value=doc_id)
                                )
                            ]
                        )
                        scroll_result = self.qdrant_client.scroll(
                            collection_name=self.collection_name,
                            scroll_filter=doc_filter,
                            limit=200  # Get more chunks per doc
                        )
                        points, _ = scroll_result
                        
                        for point in points:
                            chunk_id = point.id
                            if chunk_id in seen_exact_chunks:
                                continue
                            text = point.payload.get("text", "").lower()
                            # Check if any search term appears in text
                            for term in search_terms:
                                if term.lower() in text:
                                    seen_exact_chunks.add(chunk_id)
                                    exact_matched_chunks.append({
                                        "text": point.payload.get("text", ""),
                                        "doc_id": point.payload.get("doc_id"),
                                        "metadata": {**point.payload.get("metadata", {}), "chunk_id": str(chunk_id)},
                                        "relevance_score": 0.98,  # Very high for exact match
                                        "match_type": "exact",
                                        "matched_term": term
                                    })
                                    break  # Only add once per chunk
                    except Exception as e:
                        logger.debug(f"Error searching document {doc_id}: {e}")
            
            # Step 4: Combine and deduplicate chunks
            all_chunks = {}
            
            # Add vector search results (use result.id as chunk_id)
            for result in vector_results[:10]:  # Top 10 from vector search
                payload = result.payload
                chunk_id = str(result.id)  # Use Qdrant point ID
                if chunk_id not in all_chunks:
                    all_chunks[chunk_id] = {
                        "text": payload.get("text", ""),
                        "doc_id": payload.get("doc_id"),
                        "metadata": {**payload.get("metadata", {}), "chunk_id": chunk_id},
                        "relevance_score": result.score,
                        "match_type": "vector"
                    }
            
            # Add entity-matched chunks (higher priority)
            for chunk in entity_matched_chunks:
                chunk_id = chunk.get("metadata", {}).get("chunk_id", "")
                if chunk_id and chunk_id not in all_chunks:
                    all_chunks[chunk_id] = chunk
                elif chunk_id in all_chunks:
                    # Boost score if already found
                    all_chunks[chunk_id]["relevance_score"] = max(
                        all_chunks[chunk_id]["relevance_score"], 0.95
                    )
                    # Update match type
                    if isinstance(all_chunks[chunk_id]["match_type"], str):
                        all_chunks[chunk_id]["match_type"] = [all_chunks[chunk_id]["match_type"], "entity"]
                    elif isinstance(all_chunks[chunk_id]["match_type"], list):
                        all_chunks[chunk_id]["match_type"].append("entity")
            
            # Add exact-matched chunks (highest priority)
            for chunk in exact_matched_chunks:
                chunk_id = chunk.get("metadata", {}).get("chunk_id", "")
                if chunk_id and chunk_id not in all_chunks:
                    all_chunks[chunk_id] = chunk
                elif chunk_id in all_chunks:
                    # Boost score significantly
                    all_chunks[chunk_id]["relevance_score"] = max(
                        all_chunks[chunk_id]["relevance_score"], 0.98
                    )
                    # Update match type
                    if isinstance(all_chunks[chunk_id]["match_type"], str):
                        all_chunks[chunk_id]["match_type"] = [all_chunks[chunk_id]["match_type"], "exact"]
                    elif isinstance(all_chunks[chunk_id]["match_type"], list):
                        all_chunks[chunk_id]["match_type"].append("exact")
            
            # Sort by relevance and take top chunks
            vector_chunks = sorted(
                all_chunks.values(),
                key=lambda x: x["relevance_score"],
                reverse=True
            )[:10]  # Top 10 combined results
            
            # Extract node_ids from all chunks
            node_ids_from_chunks = set()
            for chunk in vector_chunks:
                metadata = chunk.get("metadata", {})
                if "node_ids" in metadata:
                    node_ids = metadata.get("node_ids", [])
                    if isinstance(node_ids, str):
                        node_ids = [nid.strip() for nid in node_ids.split(",") if nid.strip()]
                    if isinstance(node_ids, list):
                        node_ids_from_chunks.update(node_ids)
                
                # Extract node_ids from metadata if present
                metadata = payload.get("metadata", {})
                if "node_ids" in metadata:
                    # node_ids might be a list or comma-separated string
                    node_ids = metadata.get("node_ids", [])
                    if isinstance(node_ids, str):
                        # Handle comma-separated string
                        node_ids = [nid.strip() for nid in node_ids.split(",") if nid.strip()]
                    if isinstance(node_ids, list):
                        node_ids_from_chunks.update(node_ids)
                
                # Also check if chunk_id references a node
                chunk_id = payload.get("chunk_id")
                if chunk_id:
                    # Try to find nodes that reference this chunk using JSONB query
                    # SQLAlchemy 2.0 JSONB query syntax - use astext for text extraction
                    try:
                        nodes = session.query(Node).filter(
                            Node.properties['chunk_id'].astext == chunk_id
                        ).all()
                        for node in nodes:
                            node_ids_from_chunks.add(str(node.id))
                    except Exception:
                        # Fallback: query all nodes and filter in Python (less efficient)
                        pass
            
            # Step 5: Graph Expansion - Get 1-hop neighborhood of nodes
            graph_nodes = []
            graph_edges = []
            
            if node_ids_from_chunks:
                # Convert string UUIDs to UUID objects for querying
                from uuid import UUID as UUIDType
                import uuid as uuid_module
                node_uuids = []
                for nid in node_ids_from_chunks:
                    try:
                        # Handle both string UUIDs and UUID objects
                        if isinstance(nid, str):
                            node_uuids.append(UUIDType(nid))
                        else:
                            node_uuids.append(nid)
                    except (ValueError, TypeError):
                        continue
                
                if node_uuids:
                    # Get the nodes themselves
                    nodes = session.query(Node).filter(
                        Node.id.in_(node_uuids)
                    ).all()
                    
                    for node in nodes:
                        graph_nodes.append({
                            "id": str(node.id),
                            "label": node.label,
                            "properties": node.properties
                        })
                    
                    # Get 1-hop neighborhood (edges connected to these nodes)
                    edges = session.query(Edge).filter(
                        or_(
                            Edge.source_id.in_(node_uuids),
                            Edge.target_id.in_(node_uuids)
                        )
                    ).all()
                    
                    # Get connected nodes (targets and sources of edges)
                    connected_node_ids = set()
                    for edge in edges:
                        graph_edges.append({
                            "id": str(edge.id),
                            "source_id": str(edge.source_id),
                            "target_id": str(edge.target_id),
                            "type": edge.type,
                            "properties": edge.properties
                        })
                        connected_node_ids.add(edge.source_id)
                        connected_node_ids.add(edge.target_id)
                    
                    # Fetch connected nodes
                    if connected_node_ids:
                        connected_nodes = session.query(Node).filter(
                            Node.id.in_(list(connected_node_ids))
                        ).all()
                        
                        for node in connected_nodes:
                            # Avoid duplicates
                            if str(node.id) not in [n["id"] for n in graph_nodes]:
                                graph_nodes.append({
                                    "id": str(node.id),
                                    "label": node.label,
                                    "properties": node.properties
                                })
            
            # Step 6: Build context string for LLM with exact quotes
            context_parts = []
            
            # Add vector chunks with full text for exact matching
            context_parts.append("=" * 70)
            context_parts.append("RELEVANT TEXT CHUNKS FROM DOCUMENTS")
            context_parts.append("=" * 70)
            for i, chunk in enumerate(vector_chunks, 1):
                match_types = chunk.get("match_type", "vector")
                if isinstance(match_types, list):
                    match_types = ", ".join(match_types)
                context_parts.append(f"\n[Chunk {i}] (Match: {match_types}, Score: {chunk['relevance_score']:.3f})")
                context_parts.append(f"Source: {chunk['metadata'].get('filename', 'Unknown')}")
                if chunk['metadata'].get('page'):
                    context_parts.append(f"Page: {chunk['metadata']['page']}")
                # Include full text for exact matching (not truncated)
                context_parts.append(f"Full Text: {chunk['text']}")
            
            # Add graph context
            if graph_nodes:
                context_parts.append("\n" + "=" * 70)
                context_parts.append("RELATED CONCEPTS FROM KNOWLEDGE GRAPH")
                context_parts.append("=" * 70)
                for node in graph_nodes[:10]:  # Limit to 10 nodes
                    label = node["label"]
                    props = node["properties"]
                    name = props.get("name", props.get("label", "Unknown"))
                    description = props.get("description", "")
                    context_parts.append(f"\n• {name} ({label})")
                    if description:
                        context_parts.append(f"  Description: {description[:200]}")
            
            if graph_edges:
                context_parts.append("\n" + "=" * 70)
                context_parts.append("KEY RELATIONSHIPS")
                context_parts.append("=" * 70)
                for edge in graph_edges[:10]:  # Limit to 10 edges
                    source_node = next(
                        (n for n in graph_nodes if n["id"] == edge["source_id"]),
                        None
                    )
                    target_node = next(
                        (n for n in graph_nodes if n["id"] == edge["target_id"]),
                        None
                    )
                    source_name = (
                        source_node["properties"].get("name", "Unknown")
                        if source_node else "Unknown"
                    )
                    target_name = (
                        target_node["properties"].get("name", "Unknown")
                        if target_node else "Unknown"
                    )
                    context_parts.append(f"→ {source_name} --[{edge['type']}]--> {target_name}")
            
            context_str = "\n".join(context_parts)
            
            # Step 7: Generate answer using Ollama with strict citation requirements
            prompt = f"""You are a precise research librarian. Answer the user's question based primarily on the provided context.

QUESTION: {user_question}

CONTEXT:
{context_str}

CRITICAL INSTRUCTIONS:
1. Base your answer primarily on the context provided. Use direct quotes when they are particularly important or when the question asks for exact wording.
2. If the question asks about specific dates, times, or periods, reference the text that mentions those dates.
3. Cite the source document name and page number for EVERY fact you mention.
4. **MANDATORY CITATION FORMAT:** Use this exact format for ALL citations: [Source: filename.pdf, Page: X]
   - Example: "The experiment showed significant results [Source: research_paper.pdf, Page: 8]"
   - This format is regex-friendly and must be used consistently.
5. **CONSOLIDATE CITATIONS:** If multiple consecutive sentences come from the same page, cite it only ONCE at the end of the block. Do not repeat citations for every sentence.
   - Example (CORRECT): "The study examined various factors. The results indicated significant trends. The analysis concluded with important findings [Source: paper.pdf, Page: 5]"
   - Example (WRONG): "The study examined various factors [Source: paper.pdf, Page: 5]. The results indicated significant trends [Source: paper.pdf, Page: 5]. The analysis concluded with important findings [Source: paper.pdf, Page: 5]"
6. If the context contains the answer, use it directly. You may paraphrase when appropriate, but always cite your sources.
7. If you cannot find the answer in the context, say "I cannot find this information in the available documents."
8. For temporal queries (e.g., "between 1920 and 1930"), reference the text that mentions those dates.

ANSWER (with proper citations in the required format):"""
            
            try:
                # Direct async call - GPU-bound operation
                response = await self.ollama_client.generate(
                    model=settings.OLLAMA_MODEL,
                    prompt=prompt,
                    options={"temperature": 0.1, "top_k": 20, "top_p": 0.8}  # Lower temperature for more precise answers
                )
                
                answer = response['response'].strip()
                
                return {
                    "answer": answer,
                    "context": {
                        "vector_chunks": vector_chunks,
                        "graph_nodes": graph_nodes,
                        "graph_edges": graph_edges
                    }
                }
                
            except Exception as e:
                return {
                    "answer": f"Error generating answer: {str(e)}",
                    "context": {
                        "vector_chunks": vector_chunks,
                        "graph_nodes": graph_nodes,
                        "graph_edges": graph_edges
                    }
                }
        finally:
            session.close()
