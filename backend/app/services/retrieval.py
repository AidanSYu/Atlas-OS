"""
Retrieval Service - Hybrid RAG retrieval logic.

This is the CRITICAL FIX: Implements proper graph expansion by:
1. Querying Qdrant for top 5 text chunks
2. Extracting node_ids from Qdrant payloads
3. Querying PostgreSQL for 1-hop neighborhood of those nodes
4. Synthesizing context for LLM
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_session, Node, Edge
from app.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import ollama


class RetrievalService:
    """Handles hybrid retrieval from vector store and knowledge graph."""
    
    def __init__(self):
        self.qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.collection_name = settings.QDRANT_COLLECTION
        self.session: Session = get_session()
    
    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using Ollama."""
        response = ollama.embeddings(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            prompt=text
        )
        return response['embedding']
    
    def query_atlas(self, user_question: str) -> Dict[str, Any]:
        """
        Main retrieval function - implements the hybrid RAG workflow.
        
        Workflow:
        1. Vector Step: Query Qdrant for top 5 text chunks
        2. Graph Expansion Step: Extract node_ids from Qdrant payloads, query 1-hop neighborhood
        3. Synthesis Step: Format vector text + graph facts into prompt
        4. Generation: Send context to Ollama
        
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
        # Step 1: Vector Search - Get top 5 chunks from Qdrant
        query_embedding = self._embed_text(user_question)
        
        vector_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=5
        )
        
        if not vector_results:
            return {
                "answer": "No relevant documents found to answer this query.",
                "context": {
                    "vector_chunks": [],
                    "graph_nodes": [],
                    "graph_edges": []
                }
            }
        
        # Format vector results
        vector_chunks = []
        node_ids_from_chunks = set()
        
        for result in vector_results:
            payload = result.payload
            chunk_data = {
                "text": payload.get("text", ""),
                "doc_id": payload.get("doc_id"),
                "metadata": payload.get("metadata", {}),
                "relevance_score": result.score
            }
            vector_chunks.append(chunk_data)
            
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
                    nodes = self.session.query(Node).filter(
                        Node.properties['chunk_id'].astext == chunk_id
                    ).all()
                    for node in nodes:
                        node_ids_from_chunks.add(str(node.id))
                except Exception:
                    # Fallback: query all nodes and filter in Python (less efficient)
                    pass
        
        # Step 2: Graph Expansion - Get 1-hop neighborhood of nodes
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
                nodes = self.session.query(Node).filter(
                    Node.id.in_(node_uuids)
                ).all()
                
                for node in nodes:
                    graph_nodes.append({
                        "id": str(node.id),
                        "label": node.label,
                        "properties": node.properties
                    })
                
                # Get 1-hop neighborhood (edges connected to these nodes)
                edges = self.session.query(Edge).filter(
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
                    connected_nodes = self.session.query(Node).filter(
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
        
        # Step 3: Build context string for LLM
        context_parts = []
        
        # Add vector chunks
        context_parts.append("=" * 70)
        context_parts.append("RELEVANT TEXT CHUNKS FROM DOCUMENTS")
        context_parts.append("=" * 70)
        for i, chunk in enumerate(vector_chunks, 1):
            context_parts.append(f"\n[Chunk {i}] (Relevance: {chunk['relevance_score']:.3f})")
            context_parts.append(f"Source: {chunk['metadata'].get('filename', 'Unknown')}")
            if chunk['metadata'].get('page'):
                context_parts.append(f"Page: {chunk['metadata']['page']}")
            context_parts.append(f"Text: {chunk['text'][:500]}...")  # First 500 chars
        
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
        
        # Step 4: Generate answer using Ollama
        prompt = f"""You are an expert research assistant. Answer the user's question using ONLY the provided context.

QUESTION: {user_question}

CONTEXT:
{context_str}

INSTRUCTIONS:
1. Synthesize a comprehensive answer using the provided context
2. Cite specific sources (document names and page numbers) when referencing information
3. If information comes from the knowledge graph, mention the relationships
4. If you cannot answer from the context, say so clearly
5. Be accurate and concise

ANSWER:"""
        
        try:
            response = ollama.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                options={"temperature": 0.2, "top_k": 40, "top_p": 0.9}
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
