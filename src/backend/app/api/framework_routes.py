"""Atlas Framework API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.atlas_plugin_system import get_atlas_orchestrator, get_tool_catalog
from app.services.framework_runtime import (
    build_framework_runtime_snapshot,
    run_plugin_proof,
)
from app.services.prometheus_demo import (
    build_prometheus_demo_catalog,
    run_prometheus_demo_bundle,
    run_prometheus_demo_scenario,
)
from app.services.mwm_shadow import run_shadow_replay
from app.services.traceability_audit import run_traceability_audit
from app.core.config import settings

router = APIRouter()


class FrameworkRunRequest(BaseModel):
    prompt: str
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    max_iterations: Optional[int] = None
    conversation: List[Dict[str, str]] = Field(default_factory=list)


class FrameworkRunResponse(BaseModel):
    answer: str
    iterations: int
    model: Optional[str]
    available_tools: List[str]
    trace: List[Dict[str, Any]]


class FrameworkPluginInvokeRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class TraceabilityAuditRequest(BaseModel):
    root_node_id: str
    project_id: Optional[str] = None
    max_depth: int = 6
    graph_limit: int = 500
    domain_profile: str = "manufacturing"
    output_format: str = "prov_json"
    graph_data: Optional[Dict[str, Any]] = None
    narrate: bool = True


class TraceabilityAuditResponse(BaseModel):
    ok: bool
    root_node_id: str
    error: Optional[str] = None
    substrate: Optional[Dict[str, Any]] = None
    bundle_id: Optional[str] = None
    content_hash: Optional[str] = None
    traversal_path: List[str] = Field(default_factory=list)
    evidence_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_edges: List[Dict[str, Any]] = Field(default_factory=list)
    prov_document: Optional[Dict[str, Any]] = None
    gaps_detected: List[Dict[str, Any]] = Field(default_factory=list)
    narrative_report: Optional[str] = None
    narration: Optional[str] = None
    summary: Optional[str] = None


class MwmShadowReplayRequest(BaseModel):
    values: List[float]
    threshold_high: Optional[float] = None
    threshold_low: Optional[float] = None
    confidence: float = 0.9
    backend: str = "auto"
    adapter_path: Optional[str] = None


class MwmShadowReplayResponse(BaseModel):
    ok: bool
    summary: Optional[str] = None
    narration: Optional[str] = None
    error: Optional[str] = None
    n_points: Optional[int] = None
    threshold_high: Optional[float] = None
    threshold_low: Optional[float] = None
    confidence: Optional[float] = None
    backend_used: Optional[str] = None
    first_mwm_alert: Optional[int] = None
    first_threshold_alert: Optional[int] = None
    advance_warning_points: Optional[int] = None
    mwm_flagged_indices: List[int] = Field(default_factory=list)
    threshold_breach_indices: List[int] = Field(default_factory=list)
    changepoints: List[int] = Field(default_factory=list)
    anomaly_scores: List[float] = Field(default_factory=list)
    forecast: Optional[Dict[str, Any]] = None
    prediction_intervals: Optional[Dict[str, Any]] = None


class FrameworkPluginInvokeResponse(BaseModel):
    plugin_name: str
    status: str
    summary: str
    result: Dict[str, Any] = Field(default_factory=dict)


class FrameworkDependencyStatus(BaseModel):
    package: str
    import_name: str
    available: bool


class FrameworkGpuDevice(BaseModel):
    index: int
    name: str
    total_vram_mb: int


class FrameworkMachineProfile(BaseModel):
    platform: str
    python_version: str
    cpu_count: int
    total_ram_mb: int
    available_ram_mb: int
    torch_available: bool
    cuda_available: bool
    gpu_devices: List[FrameworkGpuDevice] = Field(default_factory=list)


class FrameworkResourceAssessment(BaseModel):
    status: str
    blockers: List[str] = Field(default_factory=list)
    advisories: List[str] = Field(default_factory=list)


class FrameworkPluginRuntimeInfo(BaseModel):
    name: str
    description: str
    source: str
    source_type: str
    license: str = ""
    loaded: bool
    load_error: Optional[str] = None
    preflight_status: str
    blocking_issues: List[str] = Field(default_factory=list)
    advisory_notes: List[str] = Field(default_factory=list)
    dependency_statuses: List[FrameworkDependencyStatus] = Field(default_factory=list)
    missing_dependencies: List[str] = Field(default_factory=list)
    supports_self_test: bool = False
    default_proof_arguments: Dict[str, Any] = Field(default_factory=dict)
    resource_assessment: FrameworkResourceAssessment


class FrameworkRuntimeResponse(BaseModel):
    status: str
    machine: FrameworkMachineProfile
    plugins: List[FrameworkPluginRuntimeInfo]


class FrameworkPluginProofRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 120.0


class FrameworkPluginProofResponse(BaseModel):
    plugin_name: str
    proof_status: str
    duration_ms: int
    summary: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    runtime: FrameworkPluginRuntimeInfo
    result: Dict[str, Any] = Field(default_factory=dict)


class FrameworkToolInfo(BaseModel):
    name: str
    description: str
    priority: int
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    tags: List[str]
    license: str = ""
    optional_dependencies: List[str] = Field(default_factory=list)
    artifacts: List[str] = Field(default_factory=list)
    resource_requirements: Dict[str, Any] = Field(default_factory=dict)
    self_test: str = ""
    fallback_used: str = ""
    source: str
    source_type: str
    loaded: bool
    load_error: Optional[str] = None


class FrameworkCatalogResponse(BaseModel):
    plugin_dir: str
    orchestrator_model: str
    core_tools: List[FrameworkToolInfo]
    plugins: List[FrameworkToolInfo]
    all_tools: List[str]


class FrameworkStatusResponse(BaseModel):
    status: str
    message: str
    plugin_dir: str
    orchestrator_model: str
    orchestrator_model_path: Optional[str] = None
    core_tool_count: int
    plugin_count: int


class PrometheusDependencyStatus(BaseModel):
    package: str
    import_name: str
    available: bool


class PrometheusPluginStatus(BaseModel):
    name: str
    title: str
    description: str
    source: str
    source_type: str
    loaded: bool
    load_error: Optional[str] = None
    status: str
    blocking_reason: Optional[str] = None
    capability_note: Optional[str] = None
    priority: int
    tags: List[str] = Field(default_factory=list)
    license: str = ""
    optional_dependencies: List[PrometheusDependencyStatus] = Field(default_factory=list)
    fallback_used: str = ""
    self_test: str = ""
    resource_requirements: Dict[str, Any] = Field(default_factory=dict)


class PrometheusScenarioInfo(BaseModel):
    id: str
    plugin_name: str
    title: str
    subtitle: str
    description: str
    recommended: bool = False
    proof_points: List[str] = Field(default_factory=list)
    status: str = "unavailable"
    blocking_reason: Optional[str] = None
    capability_note: Optional[str] = None


class PrometheusDemoCatalogResponse(BaseModel):
    framework: FrameworkStatusResponse
    plugins: List[PrometheusPluginStatus]
    scenarios: List[PrometheusScenarioInfo]


class PrometheusDemoRunRequest(BaseModel):
    scenario_id: str


class PrometheusDemoRunResponse(BaseModel):
    scenario_id: str
    plugin_name: str
    title: str
    status: str
    duration_ms: int
    summary: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)


class PrometheusDemoBundleResponse(BaseModel):
    started_at: str
    finished_at: str
    status: str
    scenario_results: List[PrometheusDemoRunResponse]


def _resolve_model_hint() -> Optional[str]:
    configured = Path(settings.MODELS_DIR) / settings.ATLAS_ORCHESTRATOR_MODEL
    if configured.exists():
        return str(configured)

    matches = sorted(Path(settings.MODELS_DIR).glob("*Orchestrator*.gguf"))
    if matches:
        return str(matches[0])
    return None


@router.get("/api/framework", response_model=FrameworkStatusResponse)
async def framework_status() -> FrameworkStatusResponse:
    """Return the active Atlas Framework status."""
    catalog = get_tool_catalog()
    catalog.refresh()
    core_tools = catalog.list_core_tools()
    plugins = catalog.list_plugins()

    return FrameworkStatusResponse(
        status="ok",
        message="Atlas Framework API is online.",
        plugin_dir=settings.ATLAS_PLUGIN_DIR,
        orchestrator_model=settings.ATLAS_ORCHESTRATOR_MODEL,
        orchestrator_model_path=_resolve_model_hint(),
        core_tool_count=len(core_tools),
        plugin_count=len(plugins),
    )


@router.get("/api/framework/health", response_model=FrameworkStatusResponse)
async def framework_health() -> FrameworkStatusResponse:
    """Health alias for the Atlas Framework API surface."""
    return await framework_status()


@router.get("/api/framework/tools", response_model=FrameworkCatalogResponse)
@router.get("/api/framework/plugins", response_model=FrameworkCatalogResponse)
async def list_framework_tools() -> FrameworkCatalogResponse:
    """Inspect the Atlas Framework tool catalog."""
    catalog = get_tool_catalog()
    catalog.refresh()
    core_tools = catalog.list_core_tools()
    plugins = catalog.list_plugins()

    return FrameworkCatalogResponse(
        plugin_dir=settings.ATLAS_PLUGIN_DIR,
        orchestrator_model=settings.ATLAS_ORCHESTRATOR_MODEL,
        core_tools=[FrameworkToolInfo(**tool) for tool in core_tools],
        plugins=[FrameworkToolInfo(**tool) for tool in plugins],
        all_tools=catalog.tool_names(),
    )


@router.post("/api/framework/run", response_model=FrameworkRunResponse)
async def run_framework(request: FrameworkRunRequest) -> FrameworkRunResponse:
    """Run the new Atlas Framework local orchestration loop."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    orchestrator = get_atlas_orchestrator()
    try:
        result = await orchestrator.run(
            prompt=request.prompt,
            project_id=request.project_id,
            session_id=request.session_id,
            max_iterations=request.max_iterations,
            conversation=request.conversation,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Atlas Framework orchestration failed: {exc}",
        ) from exc

    return FrameworkRunResponse(**result)


@router.post("/api/framework/plugins/{plugin_name}/invoke", response_model=FrameworkPluginInvokeResponse)
async def invoke_framework_plugin(
    plugin_name: str,
    request: FrameworkPluginInvokeRequest,
) -> FrameworkPluginInvokeResponse:
    """Invoke one framework plugin directly for manual inspection/testing."""
    catalog = get_tool_catalog()
    catalog.refresh()

    try:
        result = await catalog.invoke(
            plugin_name,
            dict(request.arguments),
            context=dict(request.context),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plugin invocation failed: {exc}") from exc

    valid = result.get("valid", "error" not in result)
    status = "success" if valid and not result.get("error") else "failed"
    summary = result.get("summary") or result.get("error") or "Plugin invocation completed."
    return FrameworkPluginInvokeResponse(
        plugin_name=plugin_name,
        status=status,
        summary=summary,
        result=result,
    )


@router.get("/api/framework/runtime", response_model=FrameworkRuntimeResponse)
async def get_framework_runtime() -> FrameworkRuntimeResponse:
    """Return machine-aware preflight data for all framework plugins."""
    return FrameworkRuntimeResponse(**build_framework_runtime_snapshot())


@router.post("/api/framework/plugins/{plugin_name}/proof", response_model=FrameworkPluginProofResponse)
async def prove_framework_plugin(
    plugin_name: str,
    request: FrameworkPluginProofRequest,
) -> FrameworkPluginProofResponse:
    """Run the plugin's generic proof/self-test path when available."""
    try:
        result = await run_plugin_proof(
            plugin_name,
            arguments=dict(request.arguments),
            timeout_seconds=float(request.timeout_seconds),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plugin proof failed: {exc}") from exc

    return FrameworkPluginProofResponse(**result)


@router.get("/api/framework/demos/prometheus", response_model=PrometheusDemoCatalogResponse)
async def get_prometheus_demo_catalog() -> PrometheusDemoCatalogResponse:
    """Return curated Prometheus demo scenarios and plugin readiness."""
    return PrometheusDemoCatalogResponse(**build_prometheus_demo_catalog())


@router.post("/api/framework/demos/prometheus/run", response_model=PrometheusDemoRunResponse)
async def run_prometheus_demo(request: PrometheusDemoRunRequest) -> PrometheusDemoRunResponse:
    """Run one curated Prometheus demo scenario."""
    try:
        return PrometheusDemoRunResponse(**(await run_prometheus_demo_scenario(request.scenario_id)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prometheus demo failed: {exc}") from exc


@router.post("/api/framework/demos/prometheus/run-all", response_model=PrometheusDemoBundleResponse)
async def run_prometheus_demo_all() -> PrometheusDemoBundleResponse:
    """Run the full curated Prometheus proof pack."""
    try:
        return PrometheusDemoBundleResponse(**(await run_prometheus_demo_bundle()))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prometheus proof pack failed: {exc}") from exc


@router.post("/api/framework/plugins/traceability_compliance/audit",
             response_model=TraceabilityAuditResponse)
async def traceability_audit(request: TraceabilityAuditRequest) -> TraceabilityAuditResponse:
    """End-to-end audit: fetch subgraph → build PROV bundle → narrate.

    Produces the "type a board id, get a provenance audit in under a second"
    experience the Luxshare technical lead will expect before committing.
    """
    try:
        result = await run_traceability_audit(
            root_node_id=request.root_node_id,
            project_id=request.project_id,
            max_depth=request.max_depth,
            graph_limit=request.graph_limit,
            domain_profile=request.domain_profile,
            output_format=request.output_format,
            graph_data=request.graph_data,
            narrate=request.narrate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Traceability audit failed: {exc}") from exc
    return TraceabilityAuditResponse(**result)


@router.post("/api/framework/plugins/manufacturing_world_model/shadow-replay",
             response_model=MwmShadowReplayResponse)
async def mwm_shadow_replay(request: MwmShadowReplayRequest) -> MwmShadowReplayResponse:
    """Replay a time-series through the MWM and compare to a PLC threshold alarm.

    Produces the "N points of advance warning" number the factory director
    wants to see when deciding whether to promote the model out of shadow mode.
    """
    try:
        result = await run_shadow_replay(
            values=request.values,
            threshold_high=request.threshold_high,
            threshold_low=request.threshold_low,
            confidence=request.confidence,
            backend=request.backend,
            adapter_path=request.adapter_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Shadow replay failed: {exc}") from exc
    return MwmShadowReplayResponse(**result)
