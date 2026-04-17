"""Orchestrator-backed narration of Manufacturing World Model output.

Factory directors do not read z-scores. This module turns a structured MWM
response into a short, plain-English paragraph by routing it through the same
8B Orchestrator model that drives the tool loop, using a focused single-shot
prompt. If the model is not loadable (no GGUF, no API fallback), narration
returns None and callers continue with the structured output alone.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.atlas_plugin_system import get_atlas_orchestrator

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Atlas operations narrator for a manufacturing floor. "
    "You receive one JSON object summarizing a Manufacturing World Model "
    "shadow-mode replay. Produce a single short paragraph (3-4 sentences, "
    "plain English, no bullet points, no jargon, no numbers that are not in "
    "the JSON) for a factory director. Lead with the most decision-relevant "
    "fact. If the model caught a signal before a threshold alarm, quantify "
    "the advance warning in concrete terms. If uncertainty was high, say so. "
    "Do not speculate beyond the input. Do not mention JSON, models, or "
    "conformal intervals by name."
)


def _build_payload(replay: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the director-relevant fields from a raw replay result."""
    return {
        "n_points": replay.get("n_points"),
        "first_mwm_alert": replay.get("first_mwm_alert"),
        "first_threshold_alert": replay.get("first_threshold_alert"),
        "advance_warning_points": replay.get("advance_warning_points"),
        "num_mwm_flags": len(replay.get("mwm_flagged_indices", []) or []),
        "num_threshold_breaches": len(replay.get("threshold_breach_indices", []) or []),
        "num_changepoints": len(replay.get("changepoints", []) or []),
        "backend_used": replay.get("backend_used"),
        "conformal_calibrated": bool(
            (replay.get("prediction_intervals") or {}).get("calibrated")
        ),
    }


async def narrate_shadow_replay(replay: Dict[str, Any]) -> Optional[str]:
    """Return a short English paragraph describing a shadow-mode replay.

    Returns None when the orchestrator model can't be loaded (e.g. no GGUF on
    disk and no API key) so the caller can fall back gracefully to the raw
    summary string.
    """
    if not replay.get("ok"):
        return None

    orchestrator = get_atlas_orchestrator()
    try:
        await orchestrator.ensure_model_loaded()
    except FileNotFoundError as exc:
        logger.info("Narration skipped — no orchestrator model: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Narration skipped — orchestrator load failed: %s", exc)
        return None

    payload = _build_payload(replay)
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, indent=2)},
    ]
    try:
        raw = await orchestrator._generate(messages)  # noqa: SLF001 — intentional reuse
    except Exception as exc:
        logger.warning("Narration generation failed: %s", exc)
        return None

    # The Orchestrator model may wrap prose in <think>...</think>; strip it.
    cleaned = raw
    if "<think>" in cleaned and "</think>" in cleaned:
        cleaned = cleaned.split("</think>", 1)[1]
    cleaned = cleaned.strip()
    return cleaned or None
