"""Graph service for querying nodes and edges (SQLite backend)."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.core.database import get_session, Node, Edge

import networkx as nx


class GraphService:
    """Manages knowledge graph queries."""

    def __init__(self):
        pass

    def list_nodes(
        self,
        label: Optional[str] = None,
        document_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List nodes matching criteria - only from active documents."""
        from app.core.database import Document

        session = get_session()
        try:
            query = (
                session.query(Node)
                .join(Document, Node.document_id == Document.id)
                .filter(Document.status == "completed")
            )

            if label:
                query = query.filter(Node.label == label)
            if document_id:
                query = query.filter(Node.document_id == document_id)
            if project_id:
                query = query.filter(Node.project_id == project_id)

            nodes = query.limit(limit).all()
            return [self._node_to_dict(n) for n in nodes]
        finally:
            session.close()

    def get_node_relationships(
        self, node_id: str, direction: str = "both"
    ) -> List[Dict[str, Any]]:
        """Get all relationships for a node."""
        session = get_session()
        try:
            relationships = []

            if direction in ["outgoing", "both"]:
                query = (
                    session.query(Edge)
                    .options(joinedload(Edge.source_node), joinedload(Edge.target_node))
                    .filter(Edge.source_id == node_id)
                )
                relationships.extend(query.all())

            if direction in ["incoming", "both"]:
                query = (
                    session.query(Edge)
                    .options(joinedload(Edge.source_node), joinedload(Edge.target_node))
                    .filter(Edge.target_id == node_id)
                )
                relationships.extend(query.all())

            return [self._edge_to_dict(r) for r in relationships]
        finally:
            session.close()

    def get_node_types(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all node labels (types) with counts."""
        session = get_session()
        try:
            query = session.query(Node.label, func.count(Node.id).label("count"))
            if project_id:
                query = query.filter(Node.project_id == project_id)
            results = query.group_by(Node.label).all()
            return [{"type": r[0], "count": r[1]} for r in results]
        finally:
            session.close()

    def get_full_graph(
        self,
        document_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Get all nodes and edges for a complete graph view."""
        from app.core.database import Document

        session = get_session()
        try:
            node_query = (
                session.query(Node)
                .join(Document, Node.document_id == Document.id)
                .filter(Document.status == "completed")
            )

            if document_id:
                node_query = node_query.filter(Node.document_id == document_id)
            if project_id:
                node_query = node_query.filter(Node.project_id == project_id)

            nodes = node_query.limit(limit).all()
            node_dicts = [self._node_to_dict(n) for n in nodes]
            node_ids = {n.id for n in nodes}

            edge_dicts = []
            if node_ids:
                node_id_list = list(node_ids)
                edges = (
                    session.query(Edge)
                    .options(joinedload(Edge.source_node), joinedload(Edge.target_node))
                    .filter(Edge.source_id.in_(node_id_list), Edge.target_id.in_(node_id_list))
                    .all()
                )
                edge_dicts = [self._edge_to_dict(e) for e in edges]

            return {"nodes": node_dicts, "edges": edge_dicts}
        finally:
            session.close()

    def get_networkx_subgraph(
        self,
        document_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 500,
    ) -> nx.DiGraph:
        """Build a NetworkX subgraph from the knowledge graph.

        This is used by the Navigator brain in the swarm for graph traversal,
        community detection, and path-finding algorithms.
        """
        graph_data = self.get_full_graph(
            document_id=document_id, project_id=project_id, limit=limit
        )

        G = nx.DiGraph()
        for node in graph_data["nodes"]:
            G.add_node(
                node["id"],
                name=node["name"],
                type=node["type"],
                description=node.get("description", ""),
                document_id=node.get("document_id", ""),
            )
        for edge in graph_data["edges"]:
            G.add_edge(
                edge["source_id"],
                edge["target_id"],
                type=edge["type"],
                source_name=edge.get("source_name", ""),
                target_name=edge.get("target_name", ""),
            )

        return G

    def _node_to_dict(self, node: Node) -> Dict[str, Any]:
        """Convert Node ORM object to dictionary."""
        props = node.properties or {}
        return {
            "id": str(node.id),
            "name": props.get("name", "Unknown"),
            "type": node.label,
            "description": props.get("description"),
            "document_id": str(node.document_id) if node.document_id else "",
        }

    def _edge_to_dict(self, edge: Edge) -> Dict[str, Any]:
        """Convert Edge ORM object to dictionary."""
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
            "context": edge.properties.get("context") if edge.properties else None,
        }
