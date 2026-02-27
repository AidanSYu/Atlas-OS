"""Base class for all deterministic Discovery OS plugins.

All plugins run on CPU. Models are lazy-loaded via load().
execute() must return a JSON-serializable dict (structured output, never prose).
"""
from abc import ABC, abstractmethod
from typing import Any


class BasePlugin(ABC):
    """Abstract base class for deterministic plugins.

    Every plugin must:
    1. Have a unique `name` matching the TOOL_CALL_SCHEMA enum
    2. Implement `load()` for lazy initialization
    3. Implement `execute()` for deterministic computation
    4. Declare input/output schemas for validation
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name matching the TOOL_CALL_SCHEMA action enum."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description for the LLM system prompt."""
        ...

    @abstractmethod
    async def load(self) -> Any:
        """Load model/data into memory. Called once, lazily.

        Returns an opaque handle passed to execute().
        For pure-code plugins (e.g. RDKit), return None.
        """
        ...

    @abstractmethod
    async def execute(self, model: Any, **kwargs) -> dict:
        """Run deterministic computation.

        Args:
            model: The handle returned by load().
            **kwargs: Tool-specific arguments.

        Returns:
            JSON-serializable dict with structured results.
        """
        ...

    @abstractmethod
    def input_schema(self) -> dict:
        """JSON Schema for the tool's expected input."""
        ...

    @abstractmethod
    def output_schema(self) -> dict:
        """JSON Schema for the tool's output."""
        ...
