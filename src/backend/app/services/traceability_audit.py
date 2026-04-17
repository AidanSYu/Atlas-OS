"""End-to-end traceability audit pipeline.

Chains the three independent pieces:
  1. `get_traceability_subgraph` core tool  → fetches a subgraph from the
     Atlas Rustworkx substrate (or accepts a pre-built graph).
  2. `traceability_compliance` plugin       → produces deterministic PROV-DM
     evidence bundle, compliance gaps, and template narrative.
  3. `narrate_evidence_bundle`              → turns the bundle into a short
     English paragraph via the 8B Orchestrator.

This is the "type a board id, get an audit in one second" path the Luxshare
technical lead will expect to see working before committing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.atlas_plugin_system import get_tool_catalog
from app.services.traceability_narration import narrate_evidence_bundle

PLUGIN_NAME = "traceability_compliance"
SUBGRAPH_TOOL = "get_traceability_subgraph"

logger = logging.getLogger(__name__)


async def run_traceability_audit(
    root_node_id: str,
    project_id: Optional[str] = None,
    max_depth: int = 6,
    graph_limit: int = 500,
    domain_profile: str = "manufacturing",
    output_format: str = "prov_json",
    graph_data: Optional[Dict[str, Any]] = None,
    narrate: bool = True,
) -> Dict[str, Any]:
    """Run the full audit pipeline for a single root node id.

    If `graph_data` is passed in, the substrate fetch is skipped (useful for
    demos, tests, or when the caller already knows the subgraph). Otherwise
    the `get_traceability_subgraph` core tool pulls the subgraph from the
    live Atlas graph store.
    """
    if not root_node_id:
        raise ValueError("root_node_id is required.")

    catalog = get_tool_catalog()
    catalog.refresh()

    # Step 1: resolve the subgraph
    substrate_meta: Dict[str, Any] = {"source": "provided"}
    if graph_data is None:
        subgraph = await catalog.invoke(
            SUBGRAPH_TOOL,
            {
                "root_node_id": root_node_id,
                "project_id": project_id,
                "max_depth": max_depth,
                "graph_limit": graph_limit,
            },
            context={"project_id": project_id, "caller": "traceability_audit"},
        )
        substrate_meta = {
            "source": "atlas_graph",
            "status": subgraph.get("status"),
            "substrate_summary": subgraph.get("summary"),
        }
        if subgraph.get("status") != "success":
            return {
                "ok": False,
                "root_node_id": root_node_id,
                "error": subgraph.get("summary") or "subgraph fetch failed",
                "substrate": substrate_meta,
            }
        graph_data = {
            "nodes": subgraph.get("nodes", []),
            "edges": subgraph.get("edges", []),
        }

    if not graph_data.get("nodes"):
        return {
            "ok": False,
            "root_node_id": root_node_id,
            "error": "subgraph is empty — nothing to audit",
            "substrate": substrate_meta,
        }

    # Step 2: run the plugin
    bundle = await catalog.invoke(
        PLUGIN_NAME,
        {
            "mode": "report",
            "root_node_id": root_node_id,
            "graph_data": graph_data,
            "max_depth": max_depth,
            "domain_profile": domain_profile,
            "output_format": output_format,
        },
        context={"project_id": project_id, "caller": "traceability_audit"},
    )

    if not bundle.get("valid"):
        return {
            "ok": False,
            "root_node_id": root_node_id,
            "error": bundle.get("error", "plugin returned valid=False"),
            "substrate": substrate_meta,
            "bundle": bundle,
        }

    # Step 3: optional LLM narration
    narration: Optional[str] = None
    if narrate:
        narration = await narrate_evidence_bundle(bundle)

    return {
        "ok": True,
        "root_node_id": root_node_id,
        "substrate": substrate_meta,
        "bundle_id": bundle.get("bundle_id"),
        "content_hash": bundle.get("content_hash"),
        "traversal_path": bundle.get("traversal_path", []),
        "evidence_nodes": bundle.get("evidence_nodes", []),
        "evidence_edges": bundle.get("evidence_edges", []),
        "prov_document": bundle.get("prov_document"),
        "gaps_detected": bundle.get("gaps_detected", []),
        "narrative_report": bundle.get("narrative_report"),
        "narration": narration,
        "summary": bundle.get("summary"),
    }
