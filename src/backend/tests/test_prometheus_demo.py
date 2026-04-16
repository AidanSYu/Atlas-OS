"""Targeted checks for the Prometheus demo catalog and proof endpoints."""

from __future__ import annotations

import asyncio

from app.api.framework_routes import (
    FrameworkPluginInvokeRequest,
    get_prometheus_demo_catalog,
    invoke_framework_plugin,
)
from app.services.prometheus_demo import build_prometheus_demo_catalog
from plugins.prometheus.traceability_compliance.wrapper import PLUGIN as TRACEABILITY_PLUGIN


def test_traceability_hash_is_deterministic() -> None:
    first = asyncio.run(TRACEABILITY_PLUGIN.invoke({"mode": "self_test"}))
    second = asyncio.run(TRACEABILITY_PLUGIN.invoke({"mode": "self_test"}))

    assert first.get("valid"), first
    assert second.get("valid"), second
    assert first.get("deterministic_hash") is True
    assert second.get("deterministic_hash") is True
    assert first.get("content_hash") == second.get("content_hash")


def test_prometheus_demo_catalog_contains_status_fields() -> None:
    catalog = build_prometheus_demo_catalog()

    assert catalog["framework"]["status"] == "ok"
    assert any(plugin["name"] == "traceability_compliance" for plugin in catalog["plugins"])
    assert any(scenario["id"] == "traceability_audit" for scenario in catalog["scenarios"])
    assert all("status" in plugin for plugin in catalog["plugins"])
    assert all("status" in scenario for scenario in catalog["scenarios"])


def test_prometheus_demo_catalog_route() -> None:
    payload = asyncio.run(get_prometheus_demo_catalog())

    assert payload.framework.status == "ok"
    assert any(item.name == "traceability_compliance" for item in payload.plugins)
    assert any(item.id == "line_drift_detection" for item in payload.scenarios)


def test_framework_plugin_invoke_route_for_self_test() -> None:
    response = asyncio.run(
        invoke_framework_plugin(
            "traceability_compliance",
            FrameworkPluginInvokeRequest(arguments={"mode": "self_test"}),
        )
    )

    assert response.status == "success"
    assert response.result.get("valid") is True
