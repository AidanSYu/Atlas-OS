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
