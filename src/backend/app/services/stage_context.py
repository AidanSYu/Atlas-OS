"""Cross-Store Bridge: Stage context preamble for LLM prompts.

When a Discovery OS session is active, the frontend bundles the current
epoch/artifact state and sends it as ``stage_context`` in the request body.
This module converts that dict into a system-message preamble that is
automatically prepended to every ``generate_chat()`` call for the duration
of the request.

Implementation uses ``contextvars`` so concurrent requests never leak state.
"""

import contextvars
from typing import Optional, Dict, Any, List

_stage_preamble: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "stage_context_preamble", default=None
)

STAGE_LABELS: Dict[int, str] = {
    1: "PRIME",
    2: "GENERATE",
    3: "SCREEN",
    4: "SURFACE",
    5: "SYNTHESIS_PLAN",
    6: "SPECTROSCOPY_VALIDATION",
    7: "FEEDBACK",
}


def set_stage_context_preamble(preamble: Optional[str]) -> None:
    """Set the preamble for the current asyncio task."""
    _stage_preamble.set(preamble)


def get_stage_context_preamble() -> Optional[str]:
    """Read the preamble for the current asyncio task (None when no session)."""
    return _stage_preamble.get()


def format_stage_context_preamble(
    stage_context: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Convert a ``StageContextBundle`` dict into a human-readable preamble.

    Returns ``None`` when *stage_context* is falsy or contains no active
    epoch, which means the chat should behave exactly as it does today.
    """
    if not stage_context:
        return None

    active_epoch_id: Optional[str] = stage_context.get("activeEpochId")
    active_stage: Optional[int] = stage_context.get("activeStage")

    # If no active epoch, there is nothing to prepend.
    if not active_epoch_id:
        return None

    parts: List[str] = ["You are assisting a researcher who is currently viewing:"]

    # Stage / Epoch
    if active_stage is not None:
        label = STAGE_LABELS.get(active_stage, str(active_stage))
        parts.append(f"- Stage {active_stage} ({label}) of Epoch {active_epoch_id[:8]}")

    # Target parameters
    target_params: Optional[Dict[str, Any]] = stage_context.get("targetParams")
    if target_params:
        objective = target_params.get("objective", "")
        constraints: List[Dict[str, Any]] = target_params.get("propertyConstraints", [])
        constraint_strs: List[str] = []
        for c in constraints:
            prop = c.get("property", "")
            op = c.get("operator", "")
            val = c.get("value", "")
            if isinstance(val, list) and len(val) == 2:
                constraint_strs.append(f"{prop} {val[0]}–{val[1]}")
            else:
                constraint_strs.append(f"{prop} {op} {val}")
        target_line = f"- Target: {objective}"
        if constraint_strs:
            target_line += f", {', '.join(constraint_strs)}"
        parts.append(target_line)

    # Focused candidate
    focused: Optional[Dict[str, Any]] = stage_context.get("focusedCandidate")
    focused_id: Optional[str] = stage_context.get("focusedCandidateId")
    if focused and focused_id:
        rank = focused.get("rank", "?")
        parts.append(f"- Focused on Candidate Hit #{rank} (ID: {focused_id[:8]})")
        render_data = focused.get("renderData", "")
        if render_data and isinstance(render_data, str) and len(render_data) < 200:
            parts.append(f"- Candidate data: {render_data}")
        properties: List[Dict[str, Any]] = focused.get("properties", [])
        if properties:
            prop_strs: List[str] = []
            for p in properties[:8]:
                name = p.get("name", "")
                val = p.get("value", "")
                unit = p.get("unit", "")
                passes = p.get("passesConstraint")
                flag = "\u2713" if passes else ("\u2717" if passes is False else "?")
                entry = f"{name}: {val}"
                if unit:
                    entry += f" {unit}"
                entry += f" {flag}"
                prop_strs.append(entry)
            parts.append(f"- Properties: {', '.join(prop_strs)}")

    # Active artifact summary
    artifact: Optional[Dict[str, Any]] = stage_context.get("activeArtifact")
    if artifact:
        parts.append(
            f"- Active artifact: {artifact.get('label', artifact.get('type', 'unknown'))}"
        )

    # Recent tool invocations
    tool_invocations: List[Dict[str, Any]] = stage_context.get(
        "recentToolInvocations", []
    )
    if tool_invocations:
        tools_summary = ", ".join(
            t.get("tool", "?") for t in tool_invocations[:5]
        )
        parts.append(f"- Recent tool calls: {tools_summary}")

    parts.append("")
    parts.append("Answer their question using this context and the project corpus.")

    return "\n".join(parts)
