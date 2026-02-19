
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.agents.grounding import GroundingVerifier

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate = AsyncMock()
    llm.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return llm

@pytest.fixture
def mock_qdrant():
    client = MagicMock()
    client.query_points = MagicMock()
    return client

@pytest.mark.asyncio
async def test_extract_claims_numbered_list(mock_llm, mock_qdrant):
    """Verify claim extraction from a numbered list."""
    verifier = GroundingVerifier(mock_llm, mock_qdrant, "test_collection")
    
    answer = """
    Here are the facts:
    1. Python is a programming language.
    2. Rust is memory safe.
    """
    
    mock_llm.generate.return_value = "1. Python is a programming language.\n2. Rust is memory safe."
    
    claims = await verifier._extract_claims(answer)
    assert len(claims) == 2
    assert claims[0] == "Python is a programming language."
    assert claims[1] == "Rust is memory safe."

@pytest.mark.asyncio
async def test_verify_claim_grounded(mock_llm, mock_qdrant):
    """Verify that high similarity score results in GROUNDED status."""
    verifier = GroundingVerifier(mock_llm, mock_qdrant, "test_collection")
    
    # Mock Qdrant result
    mock_point = MagicMock()
    mock_point.score = 0.95
    mock_point.payload = {"text": "Python is a popular language.", "metadata": {"filename": "source.pdf"}}
    
    mock_response = MagicMock()
    mock_response.points = [mock_point]
    mock_qdrant.query_points.return_value = mock_response
    
    claim = "Python is popular."
    result = await verifier._verify_single_claim(claim)
    
    assert result["status"] == "GROUNDED"
    assert result["confidence"] == 0.95
    assert result["source"] == "source.pdf"

@pytest.mark.asyncio
async def test_verify_claim_unverified(mock_llm, mock_qdrant):
    """Verify that low similarity score results in UNVERIFIED/INFERRED."""
    verifier = GroundingVerifier(mock_llm, mock_qdrant, "test_collection")
    
    # Mock Qdrant result
    mock_point = MagicMock()
    mock_point.score = 0.4
    
    mock_response = MagicMock()
    mock_response.points = [mock_point]
    mock_qdrant.query_points.return_value = mock_response
    
    claim = "Unrelated claim."
    result = await verifier._verify_single_claim(claim)
    
    assert result["status"] == "UNVERIFIED"
    assert result["confidence"] == 0.4
