"""
Session memory using LangGraph checkpointing.
Persists conversation state across queries within a research session.
"""
import os
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.core.config import settings

_memory_saver = None

async def get_memory_saver() -> AsyncSqliteSaver:
    """Get or create the singleton checkpoint saver."""
    global _memory_saver
    if _memory_saver is None:
        # Define memory DB path separate from main DB
        # If DATABASE_URL is sqlite:///./app.db, we want ./app_memory.db
        
        # Parse path from settings or default
        db_path = "app_memory.db"
        if hasattr(settings, "DATABASE_URL") and "sqlite" in settings.DATABASE_URL:
             base = settings.DATABASE_URL.replace("sqlite:///", "")
             db_path = base.replace(".db", "_memory.db")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
            
        # Initialize context manager
        cm = AsyncSqliteSaver.from_conn_string(db_path)
        # Manually enter context to initialize connection
        _memory_saver = await cm.__aenter__()
            
    return _memory_saver
