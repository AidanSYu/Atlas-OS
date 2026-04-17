"""Orchestrator-backed narration for traceability/compliance bundles.

The `traceability_compliance` plugin returns a deterministic evidence bundle:
node ids, edge ids, PROV document, gap list, hash. Factory directors don't
read PROV-JSON. This module routes the bundle through the 8B Orchestrator
with a focused single-shot prompt that asks for a plain-English audit
summary pitched at an ISO-style reviewer.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.atlas_plugin_system import get_atlas_orchestrator

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Atlas compliance auditor. You receive one JSON object "
    "summarizing a provenance evidence bundle for a single manufactured item. "
    "Write a short paragraph (3-5 sentences, plain English, no bullet points) "
    "for an ISO-style reviewer. Cover: what was traced, how many steps and "
    "agents were involved, which compliance gaps were detected (if any) with "
    "their severities, and the content-hash attestation. Do not invent "
    "details beyond the JSON. Do not mention JSON, PROV, or RDF by name."
)


def _build_payload(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a raw evidence bundle to the director-relevant summary fields."""
    gaps: List[Dict[str, Any]] = bundle.get("gaps_detected") or []
    gap_summary: Dict[str, int] = {}
    for gap in gaps:
        sev = str(gap.get("severity", "UNKNOWN"))
        gap_summary[sev] = gap_summary.get(sev, 0) + 1
    return {
        "root_node_id": bundle.get("root_node_id") or (
            (bundle.get("traversal_path") or [None])[0]
        ),
        "bundle_id": bundle.get("bundle_id"),
        "content_hash_prefix": (bundle.get("content_hash") or "")[:16],
        "node_count": len(bundle.get("evidence_nodes") or []),
        "edge_count": len(bundle.get("evidence_edges") or []),
        "gap_count": len(gaps),
        "gap_severity_counts": gap_summary,
        "gap_types": sorted({str(g.get("type")) for g in gaps}),
    }


async def narrate_evidence_bundle(bundle: Dict[str, Any]) -> Optional[str]:
    """Return a short English paragraph describing an evidence bundle.

    Returns None when the Orchestrator model cannot be loaded so callers
    can gracefully fall back to the deterministic narrative template.
    """
    if not bundle.get("valid"):
        return None

    orchestrator = get_atlas_orchestrator()
    try:
        await orchestrator.ensure_model_loaded()
    except FileNotFoundError as exc:
        logger.info("Traceability narration skipped — no orchestrator model: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Traceability narration skipped — orchestrator load failed: %s", exc)
        return None

    payload = _build_payload(bundle)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, indent=2)},
    ]
    try:
        raw = await orchestrator._generate(messages)  # noqa: SLF001 — intentional reuse
    except Exception as exc:
        logger.warning("Traceability narration generation failed: %s", exc)
        return None

    cleaned = raw
    if "<think>" in cleaned and "</think>" in cleaned:
        cleaned = cleaned.split("</think>", 1)[1]
    cleaned = cleaned.strip()
    return cleaned or None
