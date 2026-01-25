"""Graph service for querying nodes and edges."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.core.database import get_session, Node, Edge


class GraphService:
    """Manages knowledge graph queries."""
    
    def __init__(self):
        # Don't create session here - use per-request sessions
        pass
    
    def list_nodes(
        self,
        label: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List nodes matching criteria - only from active documents."""
        from app.core.database import Document
        session = get_session()
        try:
            # Get all active (non-deleted) document IDs
            active_docs = session.query(Document).filter(
                Document.status == "completed"
            ).all()
            active_doc_ids = [str(doc.id) for doc in active_docs]
            
            if not active_doc_ids:
                # No active documents - return empty
                return []
            
            query = session.query(Node)
            
            # Filter to only nodes from active documents using .in_() operator
            query = query.filter(
                Node.properties['document_id'].astext.in_(active_doc_ids)
            )
            
            if label:
                query = query.filter(Node.label == label)
            
            if document_id:
                try:
                    # Additional filter for specific document if provided
                    query = query.filter(
                        Node.properties['document_id'].astext == document_id
                    )
                except ValueError:
                    pass
            
            nodes = query.limit(limit).all()
            
            return [self._node_to_dict(n, session) for n in nodes]
        finally:
            session.close()
    
    def get_node_relationships(
        self,
        node_id: str,
        direction: str = "both"  # "outgoing", "incoming", "both"
    ) -> List[Dict[str, Any]]:
        """Get all relationships for a node."""
        session = get_session()
        try:
            try:
                from uuid import UUID
                node_uuid = UUID(node_id)
            except ValueError:
                return []
            
            relationships = []
            
            if direction in ["outgoing", "both"]:
                query = session.query(Edge).filter(Edge.source_id == node_uuid)
                relationships.extend(query.all())
            
            if direction in ["incoming", "both"]:
                query = session.query(Edge).filter(Edge.target_id == node_uuid)
                relationships.extend(query.all())
            
            return [self._edge_to_dict(r, session) for r in relationships]
        finally:
            session.close()
    
    def get_node_types(self) -> List[Dict[str, Any]]:
        """Get all node labels (types) with counts."""
        session = get_session()
        try:
            results = session.query(
                Node.label,
                func.count(Node.id).label('count')
            ).group_by(Node.label).all()
            
            return [{"type": r[0], "count": r[1]} for r in results]
        finally:
            session.close()
    
    def get_full_graph(self, document_id: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
        """
        Get all nodes and edges together for a complete graph view.
        ONLY returns nodes/edges from active documents - deleted documents are excluded.
        Prevents graph 'explosion' by loading everything at once.
        
        Args:
            document_id: Optional filter to get graph for specific document
            limit: Maximum number of nodes to return (default 500)
            
        Returns:
            {
                "nodes": List[Dict],
                "edges": List[Dict]
            }
        """
        from app.core.database import Document
        session = get_session()
        try:
            # Step 1: Get all active (non-deleted) document IDs
            active_docs = session.query(Document).filter(
                Document.status == "completed"
            ).all()
            active_doc_ids = [str(doc.id) for doc in active_docs]
            
            if not active_doc_ids:
                # No active documents - return empty graph
                return {
                    "nodes": [],
                    "edges": []
                }
            
            # Step 2: Get all nodes from active documents only using optimized .in_() query
            node_query = session.query(Node)
            
            # Filter to only nodes from active documents using .in_() operator
            node_query = node_query.filter(
                Node.properties['document_id'].astext.in_(active_doc_ids)
            )
            
            if document_id:
                try:
                    # Additional filter for specific document if provided
                    node_query = node_query.filter(
                        Node.properties['document_id'].astext == document_id
                    )
                except ValueError:
                    pass
            
            # Apply limit to prevent loading too many nodes
            nodes = node_query.limit(limit).all()
            node_dicts = [self._node_to_dict(n, session) for n in nodes]
            
            # Get node IDs as set for efficient lookup
            node_ids = {n.id for n in nodes}
            
            # Step 3: Get all edges where both source and target exist in the node list
            if node_ids:
                edges = session.query(Edge).filter(
                    Edge.source_id.in_(node_ids),
                    Edge.target_id.in_(node_ids)
                ).all()
                edge_dicts = [self._edge_to_dict(e, session) for e in edges]
            else:
                edge_dicts = []
            
            return {
                "nodes": node_dicts,
                "edges": edge_dicts
            }
        finally:
            session.close()
    
    def _node_to_dict(self, node: Node, session: Session) -> Dict[str, Any]:
        """Convert Node ORM object to dictionary."""
        props = node.properties or {}
        return {
            "id": str(node.id),
            "name": props.get("name", "Unknown"),
            "type": node.label,
            "description": props.get("description"),
            "document_id": props.get("document_id", "")
        }
    
    def _edge_to_dict(self, edge: Edge, session: Session) -> Dict[str, Any]:
        """Convert Edge ORM object to dictionary."""
        # Get source and target nodes
        source = session.query(Node).filter(Node.id == edge.source_id).first()
        target = session.query(Node).filter(Node.id == edge.target_id).first()
        
        source_props = source.properties if source else {}
        target_props = target.properties if target else {}
        
        return {
            "id": str(edge.id),
            "source_id": str(edge.source_id),
            "source_name": source_props.get("name", "Unknown") if source else "Unknown",
            "target_id": str(edge.target_id),
            "target_name": target_props.get("name", "Unknown") if target else "Unknown",
            "type": edge.type,
            "context": edge.properties.get("context") if edge.properties else None
        }
