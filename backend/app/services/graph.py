"""Graph service for querying nodes and edges."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
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
            # PERFORMANCE FIX A+B: Use JOIN instead of Python list filtering
            # Join Node with Document and filter on status directly in SQL
            query = session.query(Node).join(
                Document,
                Node.document_id == Document.id
            ).filter(
                Document.status == "completed"
            )
            
            if label:
                query = query.filter(Node.label == label)
            
            if document_id:
                try:
                    from uuid import UUID
                    doc_uuid = UUID(document_id)
                    query = query.filter(Node.document_id == doc_uuid)
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
            
            # PERFORMANCE FIX A: Use joinedload to eager-load source and target nodes
            # This prevents N+1 queries in _edge_to_dict
            if direction in ["outgoing", "both"]:
                query = session.query(Edge).options(
                    joinedload(Edge.source_node),
                    joinedload(Edge.target_node)
                ).filter(Edge.source_id == node_uuid)
                relationships.extend(query.all())
            
            if direction in ["incoming", "both"]:
                query = session.query(Edge).options(
                    joinedload(Edge.source_node),
                    joinedload(Edge.target_node)
                ).filter(Edge.target_id == node_uuid)
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
            # PERFORMANCE FIX B: Use JOIN instead of Python list filtering
            # Query nodes via JOIN with Document to filter by status in SQL
            node_query = session.query(Node).join(
                Document,
                Node.document_id == Document.id
            ).filter(
                Document.status == "completed"
            )
            
            if document_id:
                try:
                    from uuid import UUID
                    doc_uuid = UUID(document_id)
                    node_query = node_query.filter(Node.document_id == doc_uuid)
                except ValueError:
                    pass
            
            # Apply limit to prevent loading too many nodes
            nodes = node_query.limit(limit).all()
            node_dicts = [self._node_to_dict(n, session) for n in nodes]
            
            # Get node IDs as set for efficient lookup
            node_ids = {n.id for n in nodes}
            
            # PERFORMANCE FIX D: Get edges more efficiently
            # Option: Get edges where BOTH source and target are in the loaded nodes (safer for viz)
            # OR: Get edges where AT LEAST ONE endpoint is in loaded nodes (shows external connections)
            # Default: BOTH (safer, prevents graph explosion) - can be made configurable
            if node_ids:
                # Get edges with both endpoints in the loaded nodes
                edges = session.query(Edge).options(
                    joinedload(Edge.source_node),
                    joinedload(Edge.target_node)
                ).filter(
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
            "document_id": str(node.document_id) if node.document_id else props.get("document_id", "")
        }
    
    def _edge_to_dict(self, edge: Edge, session: Session) -> Dict[str, Any]:
        """Convert Edge ORM object to dictionary."""
        # PERFORMANCE FIX A: Use pre-loaded relationships instead of querying DB
        # Source and target nodes are already loaded via joinedload() in parent queries
        source = edge.source_node
        target = edge.target_node
        
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
