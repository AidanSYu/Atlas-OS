
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.agents.meta_router import ensure_optimal_model

@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.list_available_models = MagicMock(return_value=[
        "llama-3-8b-instruct.gguf",
        "phi-3-mini.gguf", 
        "other.gguf"
    ])
    service.active_model_name = "other.gguf"
    service.load_model = AsyncMock(return_value=True)
    return service

@pytest.mark.asyncio
async def test_swap_to_deep_model(mock_llm_service):
    """Test swapping to a deep model for complex intents."""
    await ensure_optimal_model("DEEP_DISCOVERY", mock_llm_service)
    
    # Should attempt to load llama-3
    mock_llm_service.load_model.assert_called_once()
    args = mock_llm_service.load_model.call_args[0]
    assert "llama-3" in args[0].lower()

@pytest.mark.asyncio
async def test_swap_to_fast_model(mock_llm_service):
    """Test swapping to a fast model for SIMPLE intent."""
    await ensure_optimal_model("SIMPLE", mock_llm_service)
    
    # Should attempt to load phi-3
    mock_llm_service.load_model.assert_called_once()
    args = mock_llm_service.load_model.call_args[0]
    assert "phi-3" in args[0].lower()

@pytest.mark.asyncio
async def test_no_swap_needed(mock_llm_service):
    """Test that no swap occurs if already on optimal model."""
    mock_llm_service.active_model_name = "llama-3-8b-instruct.gguf"
    
    await ensure_optimal_model("DEEP_DISCOVERY", mock_llm_service)
    
    mock_llm_service.load_model.assert_not_called()
