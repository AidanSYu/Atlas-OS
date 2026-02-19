
import pytest
import os
import asyncio
from app.core.memory import get_memory_saver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

@pytest.mark.asyncio
async def test_get_memory_saver_singleton():
    """Verify singleton behavior and initialization."""
    # Reset singleton for testing
    import app.core.memory
    app.core.memory._memory_saver = None
    
    saver1 = await get_memory_saver()
    saver2 = await get_memory_saver()
    
    assert saver1 is saver2
    assert saver1 is not None
    # Check if it has aput method (i.e. is initialized)
    assert hasattr(saver1, 'aput')

@pytest.mark.asyncio
async def test_memory_persistence_end_to_end():
    """Verify that memory saver actually saves data."""
    # Use a separate test DB for this test to avoid conflicts
    db_path = "test_memory_e2e.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Manually create saver for test control
    cm = AsyncSqliteSaver.from_conn_string(db_path)
    saver = await cm.__aenter__()
    
    try:
        config = {'configurable': {'thread_id': 't_e2e', 'checkpoint_ns': '', 'checkpoint_id': 'c1'}}
        checkpoint = {
            'v': 1, 
            'ts': '2024-01-01', 
            'id': 'c1',
            'channel_values': {'test_key': 'test_val'}, 
            'channel_versions': {}, 
            'versions_seen': {}
        }
        metadata = {'source': 'test', 'step': 1, 'writes': {}, 'parents': {}}
        
        await saver.aput(config, checkpoint, metadata, {})
        loaded = await saver.aget(config)
        
        assert loaded is not None
        assert loaded['channel_values']['test_key'] == 'test_val'
        
    finally:
        await cm.__aexit__(None, None, None)
        if os.path.exists(db_path):
            os.remove(db_path)
