"""
Session memory using LangGraph checkpointing.
Persists conversation state across queries within a research session.

Uses MemorySaver (in-process dict) instead of AsyncSqliteSaver to avoid
aiosqlite threading issues on Windows ("threads can only be started once").
Session state lives for the lifetime of the server process.
"""
from langgraph.checkpoint.memory import MemorySaver

_memory_saver: MemorySaver | None = None


async def get_memory_saver() -> MemorySaver:
    """Get or create the singleton checkpoint saver."""
    global _memory_saver
    if _memory_saver is None:
        _memory_saver = MemorySaver()
    return _memory_saver
