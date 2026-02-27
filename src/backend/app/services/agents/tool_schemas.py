"""JSON Schemas for the Discovery OS ReAct tool-calling loop.

These schemas are passed to generate_constrained() (llm.py) which uses
LlamaGrammar.from_json_schema() for local GGUF models or
response_format={"type": "json_object"} for cloud API models.

CRITICAL: The "action" enum MUST match the registered plugin names +
"search_literature" + "final_answer". Update this when adding new plugins.
"""
from typing import Any, Dict, List, Optional, Tuple

# Phase 1 available tools
PHASE1_TOOLS: List[str] = [
    "predict_properties",
    "check_toxicity",
    "search_literature",
    "final_answer",
]

# Phase 2 available tools (includes retrosynthesis)
PHASE2_TOOLS: List[str] = PHASE1_TOOLS + [
    "plan_synthesis",
]

# All tools across all phases (superset for GBNF schema enum)
ALL_DISCOVERY_TOOLS: List[str] = PHASE2_TOOLS + [
    "evaluate_strategy",
    "verify_spectrum",
]

# Phase-aware tool sets: controls which tools the LLM can call per workflow phase
PHASE_TOOLS: Dict[str, List[str]] = {
    "hit_identification": ["predict_properties", "check_toxicity", "search_literature", "final_answer"],
    "structure_design": ["predict_properties", "plan_synthesis", "check_toxicity", "search_literature", "final_answer"],
    "verification": ["verify_spectrum", "predict_properties", "search_literature", "final_answer"],
    "testing": ["predict_properties", "search_literature", "final_answer"],
}

# The core ReAct tool-call schema (GBNF-constrainable)
# Uses ALL_DISCOVERY_TOOLS so the schema covers every tool across all phases.
# The actual available tools per query are controlled by DiscoveryState.available_tools.
TOOL_CALL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "thought": {
            "type": "string",
            "description": "The agent's reasoning about what to do next",
        },
        "action": {
            "type": "string",
            "enum": ALL_DISCOVERY_TOOLS,
        },
        "action_input": {
            "type": "object",
            "description": "Arguments for the selected tool",
        },
    },
    "required": ["thought", "action", "action_input"],
}

# Per-tool input specifications used for:
#  1) System prompt (tells the model what keys each tool expects)
#  2) Input validation before dispatching (catches hallucinated keys)
#  3) Input repair (remaps common model mistakes)
TOOL_INPUT_SPECS: Dict[str, Dict[str, Any]] = {
    "predict_properties": {
        "required": ["smiles"],
        "types": {"smiles": str},
        "aliases": {
            "molecule": "smiles",
            "SMILES": "smiles",
            "mol": "smiles",
            "smi": "smiles",
            "compound": "smiles",
            "input": "smiles",
        },
    },
    "check_toxicity": {
        "required": ["smiles"],
        "types": {"smiles": str},
        "aliases": {
            "molecule": "smiles",
            "SMILES": "smiles",
            "mol": "smiles",
            "smi": "smiles",
            "compound": "smiles",
            "input": "smiles",
        },
    },
    "plan_synthesis": {
        "required": ["smiles"],
        "types": {"smiles": str},
        "aliases": {
            "molecule": "smiles",
            "SMILES": "smiles",
            "mol": "smiles",
            "smi": "smiles",
            "compound": "smiles",
            "target": "smiles",
            "input": "smiles",
        },
    },
    "evaluate_strategy": {
        "required": ["routes"],
        "types": {"routes": list},
        "aliases": {
            "route_list": "routes",
            "synthesis_routes": "routes",
            "options": "routes",
        },
    },
    "search_literature": {
        "required": ["query"],
        "types": {"query": str},
        "aliases": {
            "search": "query",
            "query_text": "query",
            "text": "query",
            "question": "query",
            "q": "query",
        },
    },
    "final_answer": {
        "required": ["query_answer"],
        "types": {"query_answer": str},
        "aliases": {
            "answer": "query_answer",
            "response": "query_answer",
            "result": "query_answer",
            "text": "query_answer",
        },
    },
    "verify_spectrum": {
        "required": ["file_path"],
        "types": {"file_path": str, "smiles": str, "tolerance": float},
        "aliases": {
            "path": "file_path",
            "jdx_file": "file_path",
            "spectrum": "file_path",
            "jdx": "file_path",
            "molecule": "smiles",
            "SMILES": "smiles",
        },
    },
}


def validate_tool_input(
    tool_name: str, action_input: Dict[str, Any]
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Validate and attempt to repair tool inputs.

    Returns:
        (is_valid, error_message, repaired_input)
        If is_valid is True, error_message is None and repaired_input may be
        the original or a corrected copy.
        If is_valid is False, repaired_input is None if unfixable, or a
        best-effort repair if possible.
    """
    spec = TOOL_INPUT_SPECS.get(tool_name)
    if spec is None:
        return (True, None, action_input)

    repaired = dict(action_input)

    # Remap aliased keys to canonical names
    for alias, canonical in spec.get("aliases", {}).items():
        if alias in repaired and canonical not in repaired:
            repaired[canonical] = repaired.pop(alias)

    # Check required keys
    missing = [k for k in spec["required"] if k not in repaired]
    if missing:
        # Last resort: if there's exactly one required key and exactly one
        # value in the input, assume the model used the wrong key name
        if len(spec["required"]) == 1 and len(repaired) == 1:
            only_key = next(iter(repaired))
            canonical = spec["required"][0]
            repaired[canonical] = repaired.pop(only_key)
            missing = []

    if missing:
        return (False, f"Missing required keys: {missing}", None)

    # Type-check values
    for key, expected_type in spec.get("types", {}).items():
        if key in repaired and not isinstance(repaired[key], expected_type):
            try:
                repaired[key] = expected_type(repaired[key])
            except (ValueError, TypeError):
                return (False, f"Key '{key}' must be {expected_type.__name__}", None)

    return (True, None, repaired)


# Keywords for fast-path DISCOVERY intent detection in meta_router.py.
# If any of these appear in the query, skip the LLM classification call.
DISCOVERY_INTENT_KEYWORDS: List[str] = [
    "molecule", "molecular", "compound", "drug", "synthesis", "synthesize",
    "SMILES", "smiles", "NMR", "spectrum", "spectral", "toxicity", "toxic",
    "binding", "solubility", "LogP", "Lipinski", "ADMET", "TPSA",
    "retrosynthesis", "property", "properties", "predict",
    "chemical", "chemistry", "pharmaceutical", "drug-like",
    "QED", "RDKit", "molecular weight",
    "verify", "jdx", "JCAMP", "peak", "peaks",
]
