"""Smoke tests for the Atlas Framework orchestration loop.

Tests use scripted model outputs in Nemotron-Orchestrator's native format:
<think> for reasoning, <tool_call> for tool delegation, and plain text
for final answers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "src" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.atlas_plugin_system.orchestrator import AtlasOrchestratorService


class FakeToolCatalog:
    """Minimal tool catalog used to exercise the orchestration loop."""

    def __init__(self) -> None:
        self.invocations: List[Dict[str, Any]] = []

    def refresh(self) -> None:
        """Match the real catalog interface."""

    def tool_names(self) -> List[str]:
        return ["search_literature", "predict_properties"]

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "search_literature",
                "description": "Search the literature database",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "name": "predict_properties",
                "description": "Predict molecular properties",
                "input_schema": {
                    "type": "object",
                    "properties": {"smiles": {"type": "string"}},
                    "required": ["smiles"],
                },
            },
        ]

    def build_openai_tools_block(self) -> str:
        lines = []
        for tool in self.list_tools():
            entry = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            lines.append(json.dumps(entry))
        return "\n".join(lines)

    async def invoke(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        self.invocations.append(
            {
                "tool_name": tool_name,
                "arguments": dict(arguments),
                "context": dict(context),
            }
        )
        if tool_name == "search_literature":
            return {
                "status": "success",
                "summary": "Ethanol appears in the local corpus with SMILES CCO.",
                "answer": "Ethanol has SMILES CCO.",
            }
        if tool_name == "predict_properties":
            return {
                "status": "success",
                "summary": "Predicted properties for CCO.",
                "properties": [
                    {
                        "smiles": "CCO",
                        "molecular_weight": 46.07,
                        "logp": -0.31,
                    }
                ],
            }
        raise AssertionError(f"Unexpected tool call: {tool_name}")


class SequencedLlama:
    """Return scripted raw completions in Nemotron's native output format."""

    def __init__(self, responses: List[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def __call__(self, _prompt: str, **_kwargs: Any) -> Dict[str, Any]:
        """Raw completion interface (not chat completion)."""
        if not self._responses:
            raise AssertionError("No more scripted llama responses were available")
        self.calls += 1
        return {
            "choices": [
                {
                    "text": self._responses.pop(0),
                }
            ]
        }


async def _load_real_orchestrator_model(service: AtlasOrchestratorService) -> None:
    """Load the real llama.cpp model or skip cleanly if unavailable."""
    try:
        await service.ensure_model_loaded()
    except FileNotFoundError as exc:
        pytest.skip(f"Orchestrator model not present: {exc}")
    except Exception as exc:
        pytest.skip(f"Unable to initialize llama-cpp-python orchestrator model: {exc}")


@pytest.mark.asyncio
async def test_orchestrator_tool_delegation_and_final_answer() -> None:
    """The orchestrator should delegate to tools via <tool_call>, then produce a final answer."""

    catalog = FakeToolCatalog()
    service = AtlasOrchestratorService(catalog=catalog)

    # Skip real model loading — inject scripted responses
    service._llama = SequencedLlama(
        [
            # Turn 1: model reasons and calls search_literature
            "<think>\nI need to find the SMILES for Ethanol first.\n</think>\n\n"
            "<tool_call>\n"
            '{"name": "search_literature", "arguments": {"query": "SMILES string for Ethanol"}}\n'
            "</tool_call>",

            # Turn 2: model calls predict_properties with the SMILES from turn 1
            "<think>\nGot SMILES CCO. Now predict its properties.\n</think>\n\n"
            "<tool_call>\n"
            '{"name": "predict_properties", "arguments": {"smiles": "CCO"}}\n'
            "</tool_call>",

            # Turn 3: model produces final answer (no tool calls)
            "<think>\nI have all the information needed.\n</think>\n\n"
            "Ethanol is represented as CCO. "
            "Its predicted molecular weight is 46.07 and logP is -0.31.",
        ]
    )
    # Mark model as loaded so ensure_model_loaded() is a no-op
    service._model_name = "test-orchestrator.gguf"

    result = await service.run(
        prompt="Find the SMILES string for Ethanol in the database, then predict its properties.",
        project_id="project-123",
        max_iterations=5,
    )

    assert result["iterations"] == 3
    assert "CCO" in result["answer"]
    assert "46.07" in result["answer"]
    assert len(result["trace"]) == 3

    # First two trace entries have tool calls, last has final_answer
    assert result["trace"][0]["tool_calls"][0]["name"] == "search_literature"
    assert result["trace"][1]["tool_calls"][0]["name"] == "predict_properties"
    assert "final_answer" in result["trace"][2]

    # Verify the tools were actually invoked
    assert [call["tool_name"] for call in catalog.invocations] == [
        "search_literature",
        "predict_properties",
    ]
    assert catalog.invocations[1]["arguments"]["smiles"] == "CCO"
    assert service._llama.calls == 3


@pytest.mark.asyncio
async def test_orchestrator_parallel_tool_calls() -> None:
    """The orchestrator should handle multiple <tool_call> blocks in a single turn."""

    catalog = FakeToolCatalog()
    service = AtlasOrchestratorService(catalog=catalog)

    service._llama = SequencedLlama(
        [
            # Turn 1: model calls both tools in parallel
            "<think>\nI'll search and predict simultaneously.\n</think>\n\n"
            "<tool_call>\n"
            '{"name": "search_literature", "arguments": {"query": "Ethanol"}}\n'
            "</tool_call>\n"
            "<tool_call>\n"
            '{"name": "predict_properties", "arguments": {"smiles": "CCO"}}\n'
            "</tool_call>",

            # Turn 2: final answer
            "Ethanol (CCO) has MW 46.07 and logP -0.31.",
        ]
    )
    service._model_name = "test-orchestrator.gguf"

    result = await service.run(prompt="Tell me about ethanol.", max_iterations=5)

    assert result["iterations"] == 2
    assert len(result["trace"][0]["tool_calls"]) == 2
    assert len(catalog.invocations) == 2


@pytest.mark.asyncio
async def test_orchestrator_no_tool_calls_returns_directly() -> None:
    """When the model produces no tool calls, return its text directly."""

    catalog = FakeToolCatalog()
    service = AtlasOrchestratorService(catalog=catalog)

    service._llama = SequencedLlama(
        [
            "<think>\nThis is a simple question I can answer directly.\n</think>\n\n"
            "Water has the chemical formula H2O.",
        ]
    )
    service._model_name = "test-orchestrator.gguf"

    result = await service.run(prompt="What is the formula for water?", max_iterations=5)

    assert result["iterations"] == 1
    assert "H2O" in result["answer"]
    assert len(catalog.invocations) == 0
