"""Coverage for generic framework runtime preflight and proof routes."""

from __future__ import annotations

import asyncio

from app.api.framework_routes import (
    FrameworkPluginProofRequest,
    get_framework_runtime,
    prove_framework_plugin,
)
from app.services.framework_runtime import build_framework_runtime_snapshot


def test_framework_runtime_snapshot_contains_machine_and_plugins() -> None:
    snapshot = build_framework_runtime_snapshot()

    assert snapshot["status"] == "ok"
    assert "machine" in snapshot
    assert isinstance(snapshot["plugins"], list)
    assert any(plugin["name"] == "traceability_compliance" for plugin in snapshot["plugins"])


def test_framework_runtime_route_exposes_preflight_data() -> None:
    response = asyncio.run(get_framework_runtime())

    assert response.status == "ok"
    assert response.machine.cpu_count >= 0
    assert any(plugin.name == "traceability_compliance" for plugin in response.plugins)


def test_framework_plugin_proof_route_runs_traceability_self_test() -> None:
    response = asyncio.run(
        prove_framework_plugin(
            "traceability_compliance",
            FrameworkPluginProofRequest(),
        )
    )

    assert response.plugin_name == "traceability_compliance"
    assert response.proof_status == "passed"
    assert response.result.get("valid") is True
    assert response.runtime.supports_self_test is True
