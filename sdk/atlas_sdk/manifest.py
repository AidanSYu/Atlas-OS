"""Manifest validation for the SDK (standalone, no backend dependency)."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    """Validated plugin manifest matching the Atlas Framework spec."""

    schema_version: str = "1.0"
    name: str
    version: str = "0.1.0"
    description: str
    entry_point: str = "wrapper.py"
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 50
    tags: List[str] = Field(default_factory=list)
    runtime: str = "python"  # python | gguf | onnx | native | generic
