
import pytest
import rustworkx as rx
import networkx as nx
import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.services.graph import GraphService

@pytest.mark.asyncio
async def test_rustworkx_subgraph():
    """Verify that get_rustworkx_subgraph returns a valid PyDiGraph and index mapping."""
    service = GraphService()
    
    # Mock get_full_graph to return dummy data
    mock_data = {
        "nodes": [
            {"id": "n1", "name": "Node A", "type": "concept", "description": "Desc A", "document_id": "d1"},
            {"id": "n2", "name": "Node B", "type": "entity", "description": "Desc B", "document_id": "d1"},
            {"id": "n3", "name": "Node C", "type": "event", "description": "Desc C", "document_id": "d2"},
        ],
        "edges": [
            {"source_id": "n1", "target_id": "n2", "type": "related_to", "source_name": "Node A", "target_name": "Node B"},
            {"source_id": "n2", "target_id": "n3", "type": "causes", "source_name": "Node B", "target_name": "Node C"},
        ]
    }
    
    # Mock the sync method that the async wrapper calls
    service.get_full_graph = MagicMock(return_value=mock_data)
    
    # Run the method
    G, id_to_idx = await service.get_rustworkx_subgraph(project_id="test_proj")
    
    # Checks
    assert isinstance(G, rx.PyDiGraph)
    assert G.num_nodes() == 3
    assert G.num_edges() == 2
    
    # Check mapping
    assert "n1" in id_to_idx
    assert "n2" in id_to_idx
    assert "n3" in id_to_idx
    
    idx1 = id_to_idx["n1"]
    idx2 = id_to_idx["n2"]
    
    # Check node data
    data1 = G.get_node_data(idx1)
    assert data1["name"] == "Node A"
    
    # Check edge existence
    assert G.has_edge(idx1, idx2)
