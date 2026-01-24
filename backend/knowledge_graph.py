"""
Knowledge Graph Module - PostgreSQL-backed property graph.

This module handles:
1. Entity storage and retrieval
2. Relationship management
3. Graph traversal and pattern matching
4. Relationship expansion for query context
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from database import Entity, Relationship, Document, get_session
import uuid
from datetime import datetime

class KnowledgeGraph:
    """Manages entities and relationships in the knowledge graph."""
    
    def __init__(self):
        self.session: Session = get_session()
    
    def add_entity(
        self,
        name: str,
        entity_type: str,
        document_id: str,
        chunk_id: Optional[str] = None,
        page_number: Optional[int] = None,
        description: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0
    ) -> str:
        """
        Add an entity to the knowledge graph.
        
        Returns:
            entity_id
        """
        # Check if entity already exists with same name and type in same document
        existing = self.session.query(Entity).filter(
            and_(
                Entity.name == name,
                Entity.entity_type == entity_type,
                Entity.document_id == document_id
            )
        ).first()
        
        if existing:
            return existing.id
        
        entity_id = str(uuid.uuid4())
        entity = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            document_id=document_id,
            chunk_id=chunk_id,
            page_number=page_number,
            description=description,
            properties=properties or {},
            confidence=confidence
        )
        
        self.session.add(entity)
        self.session.commit()
        
        return entity_id
    
    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        context: Optional[str] = None,
        document_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0
    ) -> str:
        """
        Add a relationship between two entities.
        
        Returns:
            relationship_id
        """
        # Check if relationship already exists
        existing = self.session.query(Relationship).filter(
            and_(
                Relationship.source_id == source_id,
                Relationship.target_id == target_id,
                Relationship.relationship_type == relationship_type
            )
        ).first()
        
        if existing:
            return existing.id
        
        rel_id = str(uuid.uuid4())
        relationship = Relationship(
            id=rel_id,
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            context=context,
            document_id=document_id,
            properties=properties or {},
            confidence=confidence
        )
        
        self.session.add(relationship)
        self.session.commit()
        
        return rel_id
    
    def find_entities(
        self,
        name: Optional[str] = None,
        entity_type: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Find entities matching criteria."""
        query = self.session.query(Entity)
        
        if name:
            query = query.filter(Entity.name.ilike(f"%{name}%"))
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)
        if document_id:
            query = query.filter(Entity.document_id == document_id)
        
        entities = query.limit(limit).all()
        
        return [self._entity_to_dict(e) for e in entities]
    
    def get_entity_relationships(
        self,
        entity_id: str,
        direction: str = "both",  # "outgoing", "incoming", "both"
        relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all relationships for an entity."""
        relationships = []
        
        if direction in ["outgoing", "both"]:
            query = self.session.query(Relationship).filter(
                Relationship.source_id == entity_id
            )
            if relationship_type:
                query = query.filter(Relationship.relationship_type == relationship_type)
            relationships.extend(query.all())
        
        if direction in ["incoming", "both"]:
            query = self.session.query(Relationship).filter(
                Relationship.target_id == entity_id
            )
            if relationship_type:
                query = query.filter(Relationship.relationship_type == relationship_type)
            relationships.extend(query.all())
        
        return [self._relationship_to_dict(r) for r in relationships]
    
    def find_path(
        self,
        source_entity_name: str,
        target_entity_name: str,
        max_depth: int = 3
    ) -> List[List[Dict[str, Any]]]:
        """
        Find paths between two entities.
        
        Returns list of paths, where each path is a list of:
        [entity1, relationship, entity2, relationship, entity3, ...]
        """
        # Find source and target entities
        source_entities = self.session.query(Entity).filter(
            Entity.name.ilike(f"%{source_entity_name}%")
        ).all()
        
        target_entities = self.session.query(Entity).filter(
            Entity.name.ilike(f"%{target_entity_name}%")
        ).all()
        
        if not source_entities or not target_entities:
            return []
        
        paths = []
        
        # Simple BFS for path finding
        for source in source_entities:
            for target in target_entities:
                found_paths = self._bfs_paths(source.id, target.id, max_depth)
                paths.extend(found_paths)
        
        return paths[:10]  # Limit to 10 paths
    
    def _bfs_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int
    ) -> List[List[Dict[str, Any]]]:
        """BFS to find paths between entities."""
        if source_id == target_id:
            return []
        
        # Queue: (current_entity_id, path, visited)
        queue = [(source_id, [source_id], {source_id})]
        found_paths = []
        
        while queue and len(found_paths) < 5:  # Limit results
            current_id, path, visited = queue.pop(0)
            
            if len(path) > max_depth * 2:  # path includes entities and relationships
                continue
            
            # Get outgoing relationships
            relationships = self.session.query(Relationship).filter(
                Relationship.source_id == current_id
            ).all()
            
            for rel in relationships:
                if rel.target_id not in visited:
                    new_path = path + [rel.id, rel.target_id]
                    new_visited = visited.copy()
                    new_visited.add(rel.target_id)
                    
                    if rel.target_id == target_id:
                        found_paths.append(self._format_path(new_path))
                    else:
                        queue.append((rel.target_id, new_path, new_visited))
        
        return found_paths
    
    def _format_path(self, path_ids: List[str]) -> List[Dict[str, Any]]:
        """Convert path IDs to full entity/relationship objects."""
        formatted = []
        
        for i, id_val in enumerate(path_ids):
            if i % 2 == 0:  # Entity
                entity = self.session.query(Entity).filter(Entity.id == id_val).first()
                if entity:
                    formatted.append(self._entity_to_dict(entity))
            else:  # Relationship
                rel = self.session.query(Relationship).filter(Relationship.id == id_val).first()
                if rel:
                    formatted.append(self._relationship_to_dict(rel))
        
        return formatted
    
    def expand_context(
        self,
        entity_names: List[str],
        max_hops: int = 2
    ) -> Dict[str, Any]:
        """
        Expand context around mentioned entities.
        
        Returns entities and relationships within max_hops of any mentioned entity.
        """
        # Find all mentioned entities
        entities = []
        for name in entity_names:
            found = self.session.query(Entity).filter(
                Entity.name.ilike(f"%{name}%")
            ).all()
            entities.extend(found)
        
        if not entities:
            return {"entities": [], "relationships": []}
        
        entity_ids = {e.id for e in entities}
        expanded_entities = set(entities)
        all_relationships = []
        
        # Expand by hops
        for _ in range(max_hops):
            new_entities = set()
            
            for entity_id in entity_ids:
                # Get connected entities
                rels = self.session.query(Relationship).filter(
                    or_(
                        Relationship.source_id == entity_id,
                        Relationship.target_id == entity_id
                    )
                ).all()
                
                for rel in rels:
                    all_relationships.append(rel)
                    
                    # Get connected entity
                    connected_id = rel.target_id if rel.source_id == entity_id else rel.source_id
                    connected = self.session.query(Entity).filter(Entity.id == connected_id).first()
                    
                    if connected and connected not in expanded_entities:
                        new_entities.add(connected)
            
            expanded_entities.update(new_entities)
            entity_ids = {e.id for e in new_entities}
            
            if not entity_ids:
                break
        
        return {
            "entities": [self._entity_to_dict(e) for e in expanded_entities],
            "relationships": [self._relationship_to_dict(r) for r in all_relationships]
        }
    
    def get_document_entities(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all entities from a specific document."""
        entities = self.session.query(Entity).filter(
            Entity.document_id == document_id
        ).all()
        
        return [self._entity_to_dict(e) for e in entities]
    
    def get_entity_types(self) -> List[Dict[str, Any]]:
        """Get all entity types with counts."""
        results = self.session.query(
            Entity.entity_type,
            func.count(Entity.id).label('count')
        ).group_by(Entity.entity_type).all()
        
        return [{"type": r[0], "count": r[1]} for r in results]
    
    def _entity_to_dict(self, entity: Entity) -> Dict[str, Any]:
        """Convert Entity ORM object to dictionary."""
        return {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type,
            "description": entity.description,
            "document_id": entity.document_id,
            "chunk_id": entity.chunk_id,
            "page_number": entity.page_number,
            "properties": entity.entity_properties,
            "confidence": entity.confidence
        }
    
    def _relationship_to_dict(self, rel: Relationship) -> Dict[str, Any]:
        """Convert Relationship ORM object to dictionary."""
        # Get source and target entities
        source = self.session.query(Entity).filter(Entity.id == rel.source_id).first()
        target = self.session.query(Entity).filter(Entity.id == rel.target_id).first()
        
        return {
            "id": rel.id,
            "source_id": rel.source_id,
            "source_name": source.name if source else None,
            "target_id": rel.target_id,
            "target_name": target.name if target else None,
            "type": rel.relationship_type,
            "context": rel.context,
            "document_id": rel.document_id,
            "properties": rel.rel_properties,
            "confidence": rel.confidence
        }
