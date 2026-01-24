"""Knowledge graph management."""
from typing import List, Dict, Any, Optional
from database import get_session, Node, Edge

class KnowledgeGraph:
    def __init__(self):
        pass
    
    def find_entities(self, entity_type: Optional[str] = None, document_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        session = get_session()
        try:
            query = session.query(Node)
            
            if entity_type:
                query = query.filter(Node.label == entity_type)
            
            if document_id:
                query = query.filter(Node.properties['document_id'].astext == document_id)
            
            nodes = query.limit(limit).all()
            
            return [
                {
                    "id": str(node.id),
                    "name": node.properties.get("name", ""),
                    "type": node.label,
                    "description": node.properties.get("description", ""),
                    "document_id": node.properties.get("document_id", "")
                }
                for node in nodes
            ]
        finally:
            session.close()
    
    def get_entity_relationships(self, entity_id: str, direction: str = "both") -> List[Dict[str, Any]]:
        return []  # Placeholder
    
    def get_entity_types(self) -> List[Dict[str, Any]]:
        session = get_session()
        try:
            # Get distinct entity types with counts
            result = session.query(Node.label).distinct().all()
            return [{"type": row[0], "count": 1} for row in result]
        finally:
            session.close()