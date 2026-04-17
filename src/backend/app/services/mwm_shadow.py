"""Manufacturing World Model — shadow-mode replay service.

Given a recorded or synthetic time-series plus a traditional threshold alarm
configuration, replays the trace through the MWM plugin and reports the
"advance warning" the ML model would have provided relative to the threshold
system. This is the exact narrative the factory director expects to see:
"our model flagged degradation N minutes before your PLC threshold fired."
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.atlas_plugin_system import get_tool_catalog
from app.services.mwm_narration import narrate_shadow_replay

PLUGIN_NAME = "manufacturing_world_model"


def _threshold_breaches(
    values: List[float],
    threshold_high: Optional[float],
    threshold_low: Optional[float],
) -> List[int]:
    breaches: List[int] = []
    for i, v in enumerate(values):
        if threshold_high is not None and v > threshold_high:
            breaches.append(i)
            continue
        if threshold_low is not None and v < threshold_low:
            breaches.append(i)
    return breaches


async def run_shadow_replay(
    values: List[float],
    threshold_high: Optional[float] = None,
    threshold_low: Optional[float] = None,
    confidence: float = 0.9,
    backend: str = "auto",
    adapter_path: Optional[str] = None,
    narrate: bool = True,
) -> Dict[str, Any]:
    """Run MWM in full mode against `values`, compare to threshold alarms."""
    if not values:
        raise ValueError("'values' is empty — supply a non-empty time-series.")
    if threshold_high is None and threshold_low is None:
        raise ValueError("At least one of threshold_high / threshold_low is required.")

    catalog = get_tool_catalog()
    catalog.refresh()

    mwm_result = await catalog.invoke(
        PLUGIN_NAME,
        {
            "values": values,
            "horizon": min(64, max(8, len(values) // 10)),
            "backend": backend,
            "confidence_level": confidence,
            "mode": "full",
            "adapter_path": adapter_path,
        },
        context={"caller": "mwm_shadow_replay"},
    )

    if not mwm_result.get("valid"):
        return {
            "ok": False,
            "error": mwm_result.get("error", "MWM invocation failed"),
            "mwm_result": mwm_result,
        }

    mwm_flagged: List[int] = list(mwm_result.get("anomaly_flagged_indices", []))
    changepoints: List[int] = list(mwm_result.get("changepoints", []))
    anomaly_scores: List[float] = list(mwm_result.get("anomaly_scores", []))
    breaches = _threshold_breaches(values, threshold_high, threshold_low)

    first_mwm = min(mwm_flagged) if mwm_flagged else None
    first_threshold = min(breaches) if breaches else None
    # Changepoints frequently precede anomalies — take the earliest MWM signal.
    first_mwm_any = min(
        [x for x in (first_mwm, min(changepoints) if changepoints else None) if x is not None],
        default=None,
    )

    advance_warning: Optional[int] = None
    if first_mwm_any is not None and first_threshold is not None:
        advance_warning = first_threshold - first_mwm_any

    if advance_warning is not None and advance_warning > 0:
        summary = (
            f"MWM flagged at t={first_mwm_any}; threshold alarm fired at "
            f"t={first_threshold}. Advance warning: {advance_warning} points."
        )
    elif first_threshold is None and first_mwm_any is not None:
        summary = (
            f"MWM flagged at t={first_mwm_any}; threshold alarm never fired "
            f"over this trace — MWM caught a signal the traditional system misses."
        )
    elif first_mwm_any is None and first_threshold is not None:
        summary = (
            f"Threshold alarm fired at t={first_threshold}; MWM produced no "
            f"early signal. Worth inspecting the conformal interval width at that point."
        )
    else:
        summary = "No threshold breaches and no MWM anomalies detected in this trace."

    result: Dict[str, Any] = {
        "ok": True,
        "n_points": len(values),
        "threshold_high": threshold_high,
        "threshold_low": threshold_low,
        "confidence": confidence,
        "backend_used": mwm_result.get("backend_used"),
        "first_mwm_alert": first_mwm_any,
        "first_threshold_alert": first_threshold,
        "advance_warning_points": advance_warning,
        "mwm_flagged_indices": mwm_flagged,
        "threshold_breach_indices": breaches,
        "changepoints": changepoints,
        "anomaly_scores": anomaly_scores,
        "forecast": mwm_result.get("forecast"),
        "prediction_intervals": mwm_result.get("prediction_intervals"),
        "summary": summary,
    }
    if narrate:
        result["narration"] = await narrate_shadow_replay(result)
    return result
