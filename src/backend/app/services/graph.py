"""Graph service for querying nodes and edges (SQLite backend)."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.core.database import get_session, Node, Edge

import asyncio
from async_lru import alru_cache


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
        """Get all nodes and edges for a complete graph view (Synchronous)."""
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

    @alru_cache(maxsize=32, ttl=300)
    async def get_full_graph_cached(
        self,
        document_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Async cached wrapper for UI graph loading."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, 
            lambda: self.get_full_graph(
                document_id=document_id, 
                project_id=project_id, 
                limit=limit
            )
        )

    @alru_cache(maxsize=32, ttl=300)
    async def get_rustworkx_subgraph(
        self,
        document_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 500,
    ) -> Any:
        """Build a Rustworkx subgraph (50x faster than NetworkX).
        
        Returns:
            rustworkx.PyDiGraph: Maximally performant graph object.
        """
        import rustworkx as rx

        loop = asyncio.get_running_loop()
        
        def _fetch_data():
             return self.get_full_graph(
                document_id=document_id, project_id=project_id, limit=limit
            )
            
        graph_data = await loop.run_in_executor(None, _fetch_data)

        # rustworkx uses integer indices. We must maintain a mapping.
        G = rx.PyDiGraph()
        id_to_idx = {}

        for node in graph_data["nodes"]:
            # Add node and store its data
            idx = G.add_node({
                "id": node["id"],
                "name": node["name"],
                "type": node["type"],
                "description": node.get("description", ""),
                "document_id": node.get("document_id", ""),
            })
            id_to_idx[node["id"]] = idx

        for edge in graph_data["edges"]:
            src_id = edge["source_id"]
            tgt_id = edge["target_id"]
            
            if src_id in id_to_idx and tgt_id in id_to_idx:
                G.add_edge(
                    id_to_idx[src_id], 
                    id_to_idx[tgt_id], 
                    {
                        "type": edge["type"],
                        "source_name": edge.get("source_name", ""),
                        "target_name": edge.get("target_name", ""),
                    }
                )

        return G, id_to_idx

    def invalidate_cache(self):
        """Clear all cached graph data. Call after ingestion completes."""
        try:
            self.get_full_graph_cached.cache_clear()
        except Exception:
            pass
        try:
            self.get_rustworkx_subgraph.cache_clear()
        except Exception:
            pass

    def create_or_update_feedback_node(
        self,
        hit_id: str,
        epoch_id: str,
        result_name: str,
        result_value: float,
        unit: str,
        passed: bool,
        notes: str,
        smiles: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[str]:
        """Create or update a knowledge graph node with bioassay feedback.

        Args:
            hit_id: The candidate/hit ID
            epoch_id: The epoch ID
            result_name: Name of the bioassay result (e.g., "IC50")
            result_value: Numeric result value
            unit: Unit of measurement (e.g., "μM")
            passed: Whether the test passed
            notes: Additional notes
            smiles: Optional SMILES string for the compound
            project_id: Optional project ID for scoping

        Returns:
            List of updated/created node IDs
        """
        from app.core.database import Document

        session = get_session()
        updated_nodes = []

        try:
            # Try to find an existing node matching the hit_id or SMILES
            existing_node = None

            # First, try to find by hit_id in properties
            nodes_by_hit = (
                session.query(Node)
                .filter(Node.properties.contains({"hit_id": hit_id}))
                .all()
            )
            if nodes_by_hit:
                existing_node = nodes_by_hit[0]
            elif smiles:
                # Try to find by SMILES
                nodes_by_smiles = (
                    session.query(Node)
                    .filter(Node.properties.contains({"smiles": smiles}))
                    .all()
                )
                if nodes_by_smiles:
                    existing_node = nodes_by_smiles[0]

            if existing_node:
                # Update existing node
                props = existing_node.properties or {}
                feedback_entry = {
                    "result_name": result_name,
                    "result_value": result_value,
                    "unit": unit,
                    "passed": passed,
                    "notes": notes,
                    "epoch_id": epoch_id,
                    "timestamp": asyncio.get_running_loop().time() if asyncio.get_event_loop().is_running() else 0,
                }

                # Initialize feedback_history if not present
                if "feedback_history" not in props:
                    props["feedback_history"] = []

                props["feedback_history"].append(feedback_entry)
                props["latest_feedback"] = feedback_entry

                existing_node.properties = props
                session.commit()
                updated_nodes.append(str(existing_node.id))
            else:
                # Create a new node
                # Need a document_id - use a placeholder or find/create a discovery document
                # For feedback nodes, we'll use a special document ID pattern
                import uuid
                from datetime import datetime

                node_id = str(uuid.uuid4())

                # Use a placeholder document_id - in production this might be
                # associated with a special "discovery" document
                placeholder_doc_id = f"discovery_{project_id or 'global'}"

                # Check if we have a document with this ID, otherwise use any
                doc = session.query(Document).filter(Document.id == placeholder_doc_id).first()
                if not doc:
                    # Use the first available document or create association later
                    doc = session.query(Document).first()

                document_id = doc.id if doc else placeholder_doc_id

                new_node = Node(
                    id=node_id,
                    label=hit_id,  # Use hit_id as the label
                    document_id=document_id,
                    properties={
                        "hit_id": hit_id,
                        "epoch_id": epoch_id,
                        "smiles": smiles,
                        "name": f"Candidate {hit_id[:8]}",
                        "result_name": result_name,
                        "result_value": result_value,
                        "unit": unit,
                        "passed": passed,
                        "notes": notes,
                        "feedback_history": [{
                            "result_name": result_name,
                            "result_value": result_value,
                            "unit": unit,
                            "passed": passed,
                            "notes": notes,
                            "epoch_id": epoch_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        }],
                        "latest_feedback": {
                            "result_name": result_name,
                            "result_value": result_value,
                            "unit": unit,
                            "passed": passed,
                            "notes": notes,
                            "epoch_id": epoch_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    },
                )
                session.add(new_node)
                session.commit()
                updated_nodes.append(node_id)

            return updated_nodes

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

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
