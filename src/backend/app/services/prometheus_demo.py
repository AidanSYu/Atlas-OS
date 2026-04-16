"""Curated Prometheus demo scenarios and readiness helpers."""

from __future__ import annotations

import importlib.util
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.atlas_plugin_system import get_tool_catalog
from app.core.config import settings

IMPORT_NAME_OVERRIDES = {
    "chronos-forecasting": "chronos",
    "qwen-vl-utils": "qwen_vl_utils",
}

PROMETHEUS_PLUGIN_TITLES = {
    "traceability_compliance": "Traceability & Compliance",
    "manufacturing_world_model": "Manufacturing World Model",
    "physics_simulator": "Physics Surrogate",
    "sandbox_lab": "Autonomous Sandbox Lab",
    "causal_discovery": "Causal Discovery",
    "vision_inspector": "Offline Vision Inspector",
}

PROMETHEUS_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "traceability_audit",
        "plugin_name": "traceability_compliance",
        "title": "Instant genealogy audit",
        "subtitle": "Graph walk -> provenance bundle -> ISO-style report",
        "description": "Proves a single board's full provenance chain with deterministic hashing and compliance gap detection.",
        "recommended": True,
        "proof_points": [
            "Deterministic evidence bundle",
            "W3C PROV-compatible output",
            "Compliance gaps flagged from the graph itself",
        ],
        "arguments": {"mode": "self_test"},
    },
    {
        "id": "line_drift_detection",
        "plugin_name": "manufacturing_world_model",
        "title": "Line drift detection",
        "subtitle": "Forecasting + anomaly scoring + changepoint analysis",
        "description": "Detects injected reflow drift and spike anomalies, then forecasts the line's next operating window.",
        "recommended": True,
        "proof_points": [
            "Lead indicators on synthetic line telemetry",
            "Uses a real locally installed forecasting backend",
            "Returns metrics, not just prose",
        ],
        "arguments": {"mode": "self_test"},
    },
    {
        "id": "thermal_surrogate",
        "plugin_name": "physics_simulator",
        "title": "Thermal surrogate validation",
        "subtitle": "Heat-diffusion surrogate with uncertainty and OOD checks",
        "description": "Shows a trained surrogate reproducing a heat-diffusion process and rejecting out-of-envelope conditions.",
        "recommended": True,
        "proof_points": [
            "Real PyTorch training",
            "Uncertainty estimate per prediction",
            "Out-of-distribution rejection",
        ],
        "arguments": {"mode": "self_test"},
    },
    {
        "id": "autonomous_optimization",
        "plugin_name": "sandbox_lab",
        "title": "Autonomous optimization loop",
        "subtitle": "Multi-objective experiment planner",
        "description": "Optimizes a solder reflow surface with explicit trade-offs between yield and energy.",
        "recommended": True,
        "proof_points": [
            "Batch suggestions",
            "Pareto front extraction",
            "Explicitly blocked when the BoTorch stack is absent",
        ],
        "arguments": {"mode": "self_test"},
    },
    {
        "id": "equation_discovery",
        "plugin_name": "causal_discovery",
        "title": "Equation discovery",
        "subtitle": "Lagged parent recovery and interpretable equations",
        "description": "Recovers synthetic process drivers, then produces an interpretable target equation and intervention ranking.",
        "recommended": True,
        "proof_points": [
            "Causal parent shortlist",
            "Equation string returned to the UI",
            "Explicitly blocked when Tigramite or PySR are absent",
        ],
        "arguments": {"mode": "self_test"},
    },
    {
        "id": "aoi_triage",
        "plugin_name": "vision_inspector",
        "title": "AOI triage",
        "subtitle": "Offline anomaly inspection with optional VLM adjudication",
        "description": "Runs offline defect triage on synthetic PCB imagery using PatchCore, then requires a local VLM for second-stage adjudication on flagged anomalies.",
        "recommended": True,
        "proof_points": [
            "Reference-image training step",
            "Anomaly heatmap and bounding box",
            "Explicit failure if the requested VLM stage is unavailable",
        ],
        "arguments": {"mode": "self_test", "enable_vlm": True},
    },
]


def _resolve_import_name(package: str) -> str:
    if package in IMPORT_NAME_OVERRIDES:
        return IMPORT_NAME_OVERRIDES[package]
    return package.replace("-", "_")


def _framework_status_dict(catalog) -> Dict[str, Any]:
    model_path = None
    configured = Path(settings.MODELS_DIR) / settings.ATLAS_ORCHESTRATOR_MODEL
    if configured.exists():
        model_path = str(configured)
    else:
        matches = sorted(Path(settings.MODELS_DIR).glob("*Orchestrator*.gguf"))
        if matches:
            model_path = str(matches[0])
    return {
        "status": "ok",
        "message": "Atlas Framework API is online.",
        "plugin_dir": settings.ATLAS_PLUGIN_DIR,
        "orchestrator_model": settings.ATLAS_ORCHESTRATOR_MODEL,
        "orchestrator_model_path": model_path,
        "core_tool_count": len(catalog.list_core_tools()),
        "plugin_count": len(catalog.list_plugins()),
    }


def _dependency_statuses(plugin: Dict[str, Any]) -> List[Dict[str, Any]]:
    statuses: List[Dict[str, Any]] = []
    for pkg in plugin.get("optional_dependencies", []):
        import_name = _resolve_import_name(pkg)
        statuses.append(
            {
                "package": pkg,
                "import_name": import_name,
                "available": importlib.util.find_spec(import_name) is not None,
            }
        )
    return statuses


def _dependency_map(plugin: Dict[str, Any]) -> Dict[str, bool]:
    return {
        item["package"]: bool(item["available"])
        for item in _dependency_statuses(plugin)
    }


def _plugin_readiness(plugin: Dict[str, Any]) -> Dict[str, Any]:
    if plugin.get("load_error"):
        return {
            "status": "unavailable",
            "blocking_reason": f"Plugin failed to load: {plugin['load_error']}",
            "capability_note": None,
        }

    deps = _dependency_map(plugin)
    name = plugin["name"]

    if name == "traceability_compliance":
        note = None
        if not deps.get("prov", False):
            note = "Using the built-in PROV-JSON serializer because the optional 'prov' package is not installed."
        return {"status": "ready", "blocking_reason": None, "capability_note": note}

    if name == "manufacturing_world_model":
        forecast_backends = [
            pkg
            for pkg in ("chronos-forecasting", "timesfm", "tsfm_public", "momentfm", "statsforecast")
            if deps.get(pkg, False)
        ]
        if not forecast_backends:
            return {
                "status": "unavailable",
                "blocking_reason": (
                    "No supported forecasting backend is installed. "
                    "Install one of chronos-forecasting, timesfm, tsfm_public, momentfm, or statsforecast."
                ),
                "capability_note": None,
            }
        if not deps.get("ruptures", False):
            return {
                "status": "unavailable",
                "blocking_reason": "Changepoint detection requires the 'ruptures' package.",
                "capability_note": None,
            }
        return {
            "status": "ready",
            "blocking_reason": None,
            "capability_note": "Available forecasting backends: " + ", ".join(forecast_backends) + ".",
        }

    if name == "physics_simulator":
        missing_base = [pkg for pkg in ("torch", "numpy") if not deps.get(pkg, False)]
        if missing_base:
            return {
                "status": "unavailable",
                "blocking_reason": "Physics Surrogate requires: " + ", ".join(missing_base) + ".",
                "capability_note": None,
            }
        note = None
        if not deps.get("neuraloperator", False):
            note = "Running in PINN mode; the optional FNO backend ('neuraloperator') is not installed."
        return {"status": "ready", "blocking_reason": None, "capability_note": note}

    if name == "sandbox_lab":
        missing = [pkg for pkg in ("torch", "gpytorch", "botorch") if not deps.get(pkg, False)]
        if missing:
            return {
                "status": "unavailable",
                "blocking_reason": "Sandbox Lab requires the BoTorch stack: " + ", ".join(missing) + ".",
                "capability_note": None,
            }
        return {"status": "ready", "blocking_reason": None, "capability_note": None}

    if name == "causal_discovery":
        missing = [pkg for pkg in ("tigramite", "pysr") if not deps.get(pkg, False)]
        if missing:
            return {
                "status": "unavailable",
                "blocking_reason": "Causal Discovery requires: " + ", ".join(missing) + ".",
                "capability_note": None,
            }
        return {"status": "ready", "blocking_reason": None, "capability_note": None}

    if name == "vision_inspector":
        if not deps.get("anomalib", False):
            return {
                "status": "unavailable",
                "blocking_reason": "PatchCore training and inference require the 'anomalib' package.",
                "capability_note": None,
            }
        missing_vlm = [pkg for pkg in ("torch", "transformers") if not deps.get(pkg, False)]
        if missing_vlm:
            return {
                "status": "limited",
                "blocking_reason": None,
                "capability_note": (
                    "PatchCore is available, but VLM adjudication is not. "
                    "Install torch and transformers and cache the local model weights."
                ),
            }
        return {
            "status": "ready",
            "blocking_reason": None,
            "capability_note": "Detector and VLM libraries are present. Local model weights are verified when the scenario runs.",
        }

    return {"status": "ready", "blocking_reason": None, "capability_note": None}


def _scenario_readiness(scenario: Dict[str, Any], plugin_status: Dict[str, Any]) -> Dict[str, Any]:
    plugin_readiness = plugin_status["status"]
    if plugin_readiness == "unavailable":
        return {
            "status": "unavailable",
            "blocking_reason": plugin_status.get("blocking_reason"),
            "capability_note": plugin_status.get("capability_note"),
        }
    if scenario["plugin_name"] == "vision_inspector" and plugin_readiness != "ready":
        return {
            "status": "limited",
            "blocking_reason": (
                "This AOI triage proof requires both PatchCore and the local VLM adjudication stack."
            ),
            "capability_note": plugin_status.get("capability_note"),
        }
    return {
        "status": plugin_readiness,
        "blocking_reason": plugin_status.get("blocking_reason"),
        "capability_note": plugin_status.get("capability_note"),
    }


def _catalog_prometheus_plugins(catalog) -> List[Dict[str, Any]]:
    prometheus_plugins: List[Dict[str, Any]] = []
    for plugin in catalog.list_plugins():
        if plugin["name"] not in PROMETHEUS_PLUGIN_TITLES:
            continue
        readiness = _plugin_readiness(plugin)
        prometheus_plugins.append(
            {
                "name": plugin["name"],
                "title": PROMETHEUS_PLUGIN_TITLES[plugin["name"]],
                "description": plugin["description"],
                "source": plugin["source"],
                "source_type": plugin["source_type"],
                "loaded": plugin["loaded"],
                "load_error": plugin.get("load_error"),
                "status": readiness["status"],
                "blocking_reason": readiness.get("blocking_reason"),
                "capability_note": readiness.get("capability_note"),
                "priority": plugin["priority"],
                "tags": plugin.get("tags", []),
                "license": plugin.get("license", ""),
                "optional_dependencies": _dependency_statuses(plugin),
                "fallback_used": plugin.get("fallback_used", ""),
                "self_test": plugin.get("self_test", ""),
                "resource_requirements": plugin.get("resource_requirements", {}),
            }
        )
    return sorted(prometheus_plugins, key=lambda item: item["title"])


def build_prometheus_demo_catalog() -> Dict[str, Any]:
    catalog = get_tool_catalog()
    catalog.refresh()
    framework = _framework_status_dict(catalog)
    prometheus_plugins = _catalog_prometheus_plugins(catalog)
    plugin_map = {plugin["name"]: plugin for plugin in prometheus_plugins}

    scenarios = [
        {
            "id": scenario["id"],
            "plugin_name": scenario["plugin_name"],
            "title": scenario["title"],
            "subtitle": scenario["subtitle"],
            "description": scenario["description"],
            "recommended": scenario.get("recommended", False),
            "proof_points": scenario.get("proof_points", []),
            "status": _scenario_readiness(scenario, plugin_map[scenario["plugin_name"]])["status"],
            "blocking_reason": _scenario_readiness(scenario, plugin_map[scenario["plugin_name"]]).get("blocking_reason"),
            "capability_note": _scenario_readiness(scenario, plugin_map[scenario["plugin_name"]]).get("capability_note"),
        }
        for scenario in PROMETHEUS_SCENARIOS
    ]

    return {
        "framework": framework,
        "plugins": sorted(prometheus_plugins, key=lambda item: item["title"]),
        "scenarios": scenarios,
    }


def _extract_metrics(plugin_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    if plugin_name == "traceability_compliance":
        return {
            "nodes": len(result.get("evidence_nodes", [])),
            "edges": len(result.get("evidence_edges", [])),
            "gaps": len(result.get("gaps_detected", [])),
            "deterministic_hash": result.get("deterministic_hash"),
        }
    if plugin_name == "manufacturing_world_model":
        return {
            "backend": result.get("backend_used"),
            "spike_detected": result.get("spike_detected"),
            "drift_detected": result.get("drift_detected"),
            "forecast_mae": result.get("forecast_mae"),
            "anomaly_count": len(result.get("anomaly_flagged_indices", [])),
        }
    if plugin_name == "physics_simulator":
        model_info = result.get("model_info", {})
        return {
            "model_type": model_info.get("type"),
            "final_loss": model_info.get("final_loss"),
            "ood_rejected": result.get("wild_ood_rejected", result.get("ood_rejected")),
            "mean_uncertainty": result.get("mean_uncertainty"),
        }
    if plugin_name == "sandbox_lab":
        trace = result.get("optimization_trace", [])
        return {
            "engine_used": result.get("engine_used"),
            "pareto_points": len(result.get("pareto_front", [])),
            "iterations": len(trace),
            "best_yield": result.get("best_observed", {}).get("yield_pct", {}).get("value"),
            "best_energy": result.get("best_observed", {}).get("energy_kWh", {}).get("value"),
        }
    if plugin_name == "causal_discovery":
        return {
            "engine_used": result.get("engine_used"),
            "parent_recall": result.get("parent_recall"),
            "best_equation": result.get("equations", {}).get("best_equation") if isinstance(result.get("equations"), dict) else None,
            "top_intervention": (result.get("intervention_ranking") or [{}])[0].get("variable"),
        }
    if plugin_name == "vision_inspector":
        return {
            "engine_used": result.get("engine_used"),
            "processed_images": result.get("processed_images"),
            "detected_defects": result.get("detected_defects"),
            "vlm_stage": result.get("vlm_stage"),
        }
    return {}


async def run_prometheus_demo_scenario(scenario_id: str) -> Dict[str, Any]:
    scenario = next((item for item in PROMETHEUS_SCENARIOS if item["id"] == scenario_id), None)
    if scenario is None:
        raise KeyError(f"Unknown Prometheus demo scenario: {scenario_id}")

    catalog_snapshot = build_prometheus_demo_catalog()
    scenario_snapshot = next(item for item in catalog_snapshot["scenarios"] if item["id"] == scenario_id)
    if scenario_snapshot["status"] != "ready":
        reason = scenario_snapshot.get("blocking_reason") or "Scenario is not ready on this machine."
        return {
            "scenario_id": scenario_id,
            "plugin_name": scenario["plugin_name"],
            "title": scenario["title"],
            "status": "blocked",
            "duration_ms": 0,
            "summary": reason,
            "metrics": {},
            "result": {"valid": False, "error": reason},
        }

    catalog = get_tool_catalog()
    catalog.refresh()

    started = time.perf_counter()
    result = await catalog.invoke(
        scenario["plugin_name"],
        dict(scenario.get("arguments", {})),
        context={"scenario_id": scenario_id, "demo_mode": "prometheus"},
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    valid = result.get("valid", "error" not in result)
    status = "success" if valid and not result.get("error") else "failed"
    summary = result.get("summary") or result.get("error") or "Scenario completed."

    return {
        "scenario_id": scenario_id,
        "plugin_name": scenario["plugin_name"],
        "title": scenario["title"],
        "status": status,
        "duration_ms": duration_ms,
        "summary": summary,
        "metrics": _extract_metrics(scenario["plugin_name"], result),
        "result": result,
    }


async def run_prometheus_demo_bundle() -> Dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    scenario_results: List[Dict[str, Any]] = []
    for scenario in PROMETHEUS_SCENARIOS:
        scenario_results.append(await run_prometheus_demo_scenario(scenario["id"]))

    finished_at = datetime.now(timezone.utc)
    overall_status = "success" if all(item["status"] == "success" for item in scenario_results) else "degraded"
    return {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": overall_status,
        "scenario_results": scenario_results,
    }
