"""Discovery OS state object (UCSO - Universal Chemical State Object).

This is a TypedDict (NOT Pydantic) because LangGraph StateGraph nodes
must read/write TypedDict states. Pydantic BaseModel instances cause
serialization mismatches at node boundaries.

All values are plain dicts, lists, strings, numbers -- no class instances.
"""
from typing import Any, Dict, List, TypedDict


class DiscoveryState(TypedDict, total=False):
    """State object for the Discovery workflow.

    Every node reads from and writes to this structure.
    Plain dicts and lists only -- no Pydantic models inside.
    """

    # --- User intent ---
    query: str
    project_id: str
    target_constraints: Dict[str, Any]  # Phase 2+: structured constraints from intent parsing

    # --- Tool calling state ---
    messages: List[Dict[str, Any]]
    # ReAct message history:
    # [{"role": "assistant", "thought": ..., "action": ..., "action_input": ...},
    #  {"role": "tool", "name": ..., "output": ...}]
    current_iteration: int       # 0-indexed, max MAX_TOOL_ITERATIONS
    available_tools: List[str]   # Dynamic -- changes per workflow phase

    # --- Accumulated scientific data ---
    candidates: List[Dict[str, Any]]
    # Each: {"smiles": str, "properties": dict, "toxicity": dict|None}

    # --- Workflow tracking ---
    phase: str  # "hit_identification" | "structure_design" | "verification" | "testing"
    reasoning_trace: List[str]
    status: str  # "running" | "completed" | "error" | "max_iterations"

    # --- Spectrum verification (Phase 3) ---
    spectrum_file_path: str  # Absolute path to uploaded .jdx file

    # --- Experimental results (Phase 4) ---
    assay_result: Dict[str, Any]
    # Biological assay data, e.g. {"IC50_nM": 45, "target": "EGFR", "date": "2026-02-27"}
    experiment_node_id: str
    # UUID of the SynthesisAttempt Node written to the knowledge graph after verification

    # --- Output ---
    final_answer: str
    evidence: List[Dict[str, Any]]
    confidence_score: float
