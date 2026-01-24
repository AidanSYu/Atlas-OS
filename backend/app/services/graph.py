"""Graph service for querying nodes and edges."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.core.database import get_session, Node, Edge


class GraphService:
    """Manages knowledge graph queries."""
    
    def __init__(self):
        self.session: Session = get_session()
    
    def list_nodes(
        self,
        label: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List nodes matching criteria."""
        query = self.session.query(Node)
        
        if label:
            query = query.filter(Node.label == label)
        
        if document_id:
            try:
                from uuid import UUID
                doc_uuid = UUID(document_id)
                # Query nodes where properties contain document_id
                query = query.filter(
                    Node.properties['document_id'].astext == document_id
                )
            except ValueError:
                pass
        
        nodes = query.limit(limit).all()
        
        return [self._node_to_dict(n) for n in nodes]
    
    def get_node_relationships(
        self,
        node_id: str,
        direction: str = "both"  # "outgoing", "incoming", "both"
    ) -> List[Dict[str, Any]]:
        """Get all relationships for a node."""
        try:
            from uuid import UUID
            node_uuid = UUID(node_id)
        except ValueError:
            return []
        
        relationships = []
        
        if direction in ["outgoing", "both"]:
            query = self.session.query(Edge).filter(Edge.source_id == node_uuid)
            relationships.extend(query.all())
        
        if direction in ["incoming", "both"]:
            query = self.session.query(Edge).filter(Edge.target_id == node_uuid)
            relationships.extend(query.all())
        
        return [self._edge_to_dict(r) for r in relationships]
    
    def get_node_types(self) -> List[Dict[str, Any]]:
        """Get all node labels (types) with counts."""
        results = self.session.query(
            Node.label,
            func.count(Node.id).label('count')
        ).group_by(Node.label).all()
        
        return [{"type": r[0], "count": r[1]} for r in results]
    
    def _node_to_dict(self, node: Node) -> Dict[str, Any]:
        """Convert Node ORM object to dictionary."""
        props = node.properties or {}
        return {
            "id": str(node.id),
            "name": props.get("name", "Unknown"),
            "type": node.label,
            "description": props.get("description"),
            "document_id": props.get("document_id", "")
        }
    
    def _edge_to_dict(self, edge: Edge) -> Dict[str, Any]:
        """Convert Edge ORM object to dictionary."""
        # Get source and target nodes
        source = self.session.query(Node).filter(Node.id == edge.source_id).first()
        target = self.session.query(Node).filter(Node.id == edge.target_id).first()
        
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
