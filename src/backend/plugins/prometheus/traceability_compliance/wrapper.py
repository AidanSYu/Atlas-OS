"""Traceability & Compliance Engine — fully self-contained, no app imports.

Generates deterministic provenance evidence bundles and ISO-style compliance
reports from knowledge graph walks using W3C PROV-DM semantics.

The LLM is the narrator, not the source of truth: this plugin emits a
deterministic evidence bundle (exact node IDs, edge IDs, timestamps, hashes,
traversal path) plus a human-readable report template. The Orchestrator's
synthesis model turns the template into an ISO-style narrative.
"""
import hashlib
import json
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain profiles: map generic graph node types to W3C PROV-DM types
# ---------------------------------------------------------------------------

DOMAIN_PROFILES: Dict[str, Dict[str, str]] = {
    "manufacturing": {
        "product": "Entity", "component": "Entity", "material": "Entity",
        "batch": "Entity", "board": "Entity", "lot": "Entity",
        "process": "Activity", "assembly": "Activity", "test": "Activity",
        "inspection": "Activity", "reflow": "Activity",
        "equipment": "Agent", "operator": "Agent", "machine": "Agent",
        "line": "Agent", "oven": "Agent",
    },
    "biotech": {
        "batch": "Entity", "sample": "Entity", "reagent": "Entity",
        "compound": "Entity", "plate": "Entity",
        "assay": "Activity", "synthesis": "Activity", "purification": "Activity",
        "qc_test": "Activity",
        "analyst": "Agent", "instrument": "Agent", "lab": "Agent",
    },
    "supply_chain": {
        "shipment": "Entity", "package": "Entity", "document": "Entity",
        "order": "Entity",
        "transit": "Activity", "customs": "Activity", "receiving": "Activity",
        "carrier": "Agent", "warehouse": "Agent", "supplier": "Agent",
    },
    "generic": {},  # no mapping — use explicit type field from node data
}

# PROV-DM relation types
PROV_RELATIONS = {
    "used", "wasGeneratedBy", "wasDerivedFrom",
    "wasAssociatedWith", "wasAttributedTo", "actedOnBehalfOf",
}


def _resolve_prov_type(node_type: str, profile: Dict[str, str]) -> str:
    """Map a domain node type to a PROV-DM type (Entity/Activity/Agent)."""
    lower = node_type.lower()
    if lower in profile:
        return profile[lower]
    # Fallback: check if the type itself is a PROV type
    if node_type in ("Entity", "Activity", "Agent"):
        return node_type
    return "Entity"  # safe default


def _compute_hash(data: Any) -> str:
    """SHA-256 of canonical JSON serialization."""
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_prov_document(
    nodes: List[Dict], edges: List[Dict], profile: Dict[str, str]
) -> Dict[str, Any]:
    """Build a PROV-DM compliant document from graph nodes and edges.

    Uses the prov library if available, otherwise builds PROV-JSON manually.
    """
    try:
        import prov.model as prov_model
        return _build_prov_with_library(nodes, edges, profile, prov_model)
    except ImportError:
        return _build_prov_manual(nodes, edges, profile)


def _build_prov_with_library(
    nodes: List[Dict], edges: List[Dict], profile: Dict[str, str], prov_model: Any
) -> Dict[str, Any]:
    """Build PROV document using the prov Python library."""
    doc = prov_model.ProvDocument()
    doc.set_default_namespace("urn:atlas:prov:")

    refs: Dict[str, Any] = {}
    factories = {
        "Entity": doc.entity,
        "Activity": doc.activity,
        "Agent": doc.agent,
    }

    for node in nodes:
        node_id = node["id"]
        node_type = node.get("type", "Entity")
        prov_type = _resolve_prov_type(node_type, profile)
        metadata = dict(node.get("metadata", {}))
        metadata["prov:type"] = node_type
        factory = factories.get(prov_type, doc.entity)
        refs[node_id] = factory(node_id, metadata)

    relation_map = {
        "used": doc.used,
        "wasGeneratedBy": doc.wasGeneratedBy,
        "wasDerivedFrom": doc.wasDerivedFrom,
        "wasAssociatedWith": doc.wasAssociatedWith,
        "wasAttributedTo": doc.wasAttributedTo,
        "actedOnBehalfOf": doc.actedOnBehalfOf,
    }

    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        rel = edge.get("relation", "wasDerivedFrom")
        if src in refs and tgt in refs and rel in relation_map:
            relation_map[rel](refs[src], refs[tgt])

    return json.loads(doc.serialize(format="json"))


def _build_prov_manual(
    nodes: List[Dict], edges: List[Dict], profile: Dict[str, str]
) -> Dict[str, Any]:
    """Build PROV-JSON manually without the prov library."""
    doc: Dict[str, Any] = {
        "prefix": {"default": "urn:atlas:prov:", "prov": "http://www.w3.org/ns/prov#"},
        "entity": {},
        "activity": {},
        "agent": {},
    }

    for node in nodes:
        node_id = node["id"]
        prov_type = _resolve_prov_type(node.get("type", "Entity"), profile)
        section = prov_type.lower()
        if section not in doc:
            section = "entity"
        attrs = dict(node.get("metadata", {}))
        attrs["prov:type"] = node.get("type", "Entity")
        doc[section][f"default:{node_id}"] = attrs

    for edge in edges:
        rel = edge.get("relation", "wasDerivedFrom")
        if rel not in doc:
            doc[rel] = {}
        edge_id = edge.get("id") or _compute_hash(
            {"source": edge.get("source"), "target": edge.get("target"), "relation": rel}
        )[:12]
        doc[rel][edge_id] = {
            f"prov:{_get_prov_role(rel, 'source')}": f"default:{edge['source']}",
            f"prov:{_get_prov_role(rel, 'target')}": f"default:{edge['target']}",
        }

    return doc


def _get_prov_role(relation: str, end: str) -> str:
    """Map relation + endpoint to PROV-JSON role names."""
    roles = {
        "used": ("activity", "entity"),
        "wasGeneratedBy": ("entity", "activity"),
        "wasDerivedFrom": ("generatedEntity", "usedEntity"),
        "wasAssociatedWith": ("activity", "agent"),
        "wasAttributedTo": ("entity", "agent"),
        "actedOnBehalfOf": ("delegate", "responsible"),
    }
    pair = roles.get(relation, ("subject", "object"))
    return pair[0] if end == "source" else pair[1]


def _bfs_walk(
    nodes: List[Dict], edges: List[Dict], root_id: str, max_depth: int
) -> tuple:
    """BFS walk from root_id, returning (visited_nodes, visited_edges, path)."""
    node_map = {n["id"]: n for n in nodes}
    adjacency: Dict[str, List[Dict]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source"], []).append(edge)
        adjacency.setdefault(edge["target"], []).append(edge)

    visited_nodes: List[Dict] = []
    visited_edges: List[Dict] = []
    visited_ids: set = set()
    visited_edge_ids: set = set()
    path: List[str] = []

    queue: deque = deque([(root_id, 0)])
    visited_ids.add(root_id)

    while queue:
        current_id, depth = queue.popleft()
        if current_id in node_map:
            visited_nodes.append(node_map[current_id])
            path.append(current_id)

        if depth >= max_depth:
            continue

        for edge in adjacency.get(current_id, []):
            edge_id = edge.get("id", f"{edge['source']}->{edge['target']}")
            if edge_id in visited_edge_ids:
                continue
            visited_edge_ids.add(edge_id)
            visited_edges.append(edge)

            neighbor = edge["target"] if edge["source"] == current_id else edge["source"]
            if neighbor not in visited_ids:
                visited_ids.add(neighbor)
                queue.append((neighbor, depth + 1))

    return visited_nodes, visited_edges, path


def _detect_gaps(nodes: List[Dict], edges: List[Dict], profile: Dict[str, str]) -> List[Dict]:
    """Detect compliance gaps: activities without agents, unsigned steps, etc."""
    gaps: List[Dict] = []
    activities = {n["id"] for n in nodes if _resolve_prov_type(n.get("type", ""), profile) == "Activity"}
    agent_associations = {e["source"] for e in edges if e.get("relation") == "wasAssociatedWith"}

    for act_id in activities:
        if act_id not in agent_associations:
            gaps.append({
                "type": "missing_agent",
                "node_id": act_id,
                "severity": "HIGH",
                "description": f"Activity '{act_id}' has no associated agent (operator/equipment).",
            })

    entities_with_generation = {e["source"] for e in edges if e.get("relation") == "wasGeneratedBy"}
    entities = {n["id"] for n in nodes if _resolve_prov_type(n.get("type", ""), profile) == "Entity"}
    for ent_id in entities:
        if ent_id not in entities_with_generation:
            has_derivation = any(
                e["source"] == ent_id and e.get("relation") == "wasDerivedFrom" for e in edges
            )
            if not has_derivation:
                gaps.append({
                    "type": "missing_provenance",
                    "node_id": ent_id,
                    "severity": "MEDIUM",
                    "description": f"Entity '{ent_id}' has no generation activity or derivation source.",
                })

    return gaps


def _generate_narrative(
    visited_nodes: List[Dict], visited_edges: List[Dict],
    gaps: List[Dict], bundle_id: str, content_hash: str
) -> str:
    """Generate a structured ISO-style narrative report template."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sections = [
        "=" * 60,
        "PROVENANCE & COMPLIANCE REPORT",
        "=" * 60,
        "",
        f"Bundle ID:     {bundle_id}",
        f"Generated:     {now}",
        f"Content Hash:  SHA-256:{content_hash}",
        f"Nodes:         {len(visited_nodes)}",
        f"Relationships: {len(visited_edges)}",
        "",
        "-" * 40,
        "1. PROVENANCE CHAIN",
        "-" * 40,
    ]

    for i, node in enumerate(visited_nodes, 1):
        meta_str = ", ".join(f"{k}={v}" for k, v in node.get("metadata", {}).items())
        sections.append(f"  [{i}] {node['id']} ({node.get('type', 'Entity')})")
        if meta_str:
            sections.append(f"      Attributes: {meta_str}")

    sections.extend(["", "-" * 40, "2. RELATIONSHIPS", "-" * 40])
    for edge in visited_edges:
        sections.append(f"  {edge['source']} --[{edge.get('relation', '?')}]--> {edge['target']}")

    sections.extend(["", "-" * 40, "3. COMPLIANCE GAPS", "-" * 40])
    if gaps:
        for gap in gaps:
            sections.append(f"  [{gap['severity']}] {gap['type']}: {gap['description']}")
    else:
        sections.append("  No compliance gaps detected.")

    sections.extend([
        "",
        "-" * 40,
        "4. HASH ATTESTATION",
        "-" * 40,
        f"  This report's evidence bundle has content hash SHA-256:{content_hash}.",
        "  Any modification to the underlying graph data will produce a different hash.",
        "",
        "-" * 40,
        "5. SIGN-OFF",
        "-" * 40,
        "  Auditor: ____________________",
        "  Date:    ____________________",
        "  Disposition: [ ] ACCEPT  [ ] REJECT  [ ] HOLD",
        "",
        "=" * 60,
    ])

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Demo data for self-test
# ---------------------------------------------------------------------------

DEMO_GRAPH = {
    "nodes": [
        {"id": "board-8842", "type": "product", "metadata": {"lot": "B8842", "pn": "PCBA-X100"}},
        {"id": "solder-lot-L123", "type": "material", "metadata": {"supplier": "Kester", "alloy": "SAC305"}},
        {"id": "paste-stencil-S45", "type": "material", "metadata": {"aperture": "0.12mm"}},
        {"id": "reflow-oven-Z", "type": "equipment", "metadata": {"model": "Heller-1809", "cal_date": "2026-03-01"}},
        {"id": "smt-line-3", "type": "line", "metadata": {"facility": "Plant-A"}},
        {"id": "tech-T456", "type": "operator", "metadata": {"cert": "IPC-A-610-CIS", "shift": "A"}},
        {"id": "paste-deposition", "type": "process", "metadata": {"start": "2026-04-15T08:30:00Z", "end": "2026-04-15T08:45:00Z"}},
        {"id": "component-placement", "type": "assembly", "metadata": {"start": "2026-04-15T08:50:00Z", "end": "2026-04-15T09:00:00Z"}},
        {"id": "reflow-soldering", "type": "reflow", "metadata": {"start": "2026-04-15T09:00:00Z", "end": "2026-04-15T09:45:00Z", "peak_temp_c": 245}},
        {"id": "aoi-inspection", "type": "inspection", "metadata": {"start": "2026-04-15T09:50:00Z", "result": "PASS"}},
        {"id": "ict-test-001", "type": "test", "metadata": {"start": "2026-04-15T10:00:00Z", "result": "PASS", "fixture": "ICT-F12"}},
    ],
    "edges": [
        {"id": "e-01", "source": "paste-deposition", "target": "solder-lot-L123", "relation": "used"},
        {"id": "e-02", "source": "paste-deposition", "target": "paste-stencil-S45", "relation": "used"},
        {"id": "e-03", "source": "paste-deposition", "target": "tech-T456", "relation": "wasAssociatedWith"},
        {"id": "e-04", "source": "paste-deposition", "target": "smt-line-3", "relation": "wasAssociatedWith"},
        {"id": "e-05", "source": "component-placement", "target": "smt-line-3", "relation": "wasAssociatedWith"},
        {"id": "e-06", "source": "reflow-soldering", "target": "reflow-oven-Z", "relation": "wasAssociatedWith"},
        {"id": "e-07", "source": "reflow-soldering", "target": "tech-T456", "relation": "wasAssociatedWith"},
        {"id": "e-08", "source": "board-8842", "target": "reflow-soldering", "relation": "wasGeneratedBy"},
        {"id": "e-09", "source": "board-8842", "target": "solder-lot-L123", "relation": "wasDerivedFrom"},
        {"id": "e-10", "source": "aoi-inspection", "target": "board-8842", "relation": "used"},
        {"id": "e-11", "source": "aoi-inspection", "target": "smt-line-3", "relation": "wasAssociatedWith"},
        {"id": "e-12", "source": "ict-test-001", "target": "board-8842", "relation": "used"},
    ],
}


class TraceabilityComplianceWrapper:
    """W3C PROV-DM based traceability and compliance engine."""

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {}
        mode = args.get("mode", "trace")

        if mode == "self_test":
            return await self._run_self_test()

        graph_data = args.get("graph_data", {})
        root_node_id = args.get("root_node_id", "")
        max_depth = int(args.get("max_depth", 10))
        domain_profile_name = args.get("domain_profile", "generic")
        profile = DOMAIN_PROFILES.get(domain_profile_name, DOMAIN_PROFILES["generic"])

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        if not nodes:
            return {"valid": False, "error": "No graph data provided. Supply graph_data with nodes and edges."}

        # If no root specified, use first node
        if not root_node_id:
            root_node_id = nodes[0]["id"] if nodes else ""

        # BFS walk
        visited_nodes, visited_edges, path = _bfs_walk(nodes, edges, root_node_id, max_depth)

        if not visited_nodes:
            return {"valid": False, "error": f"Root node '{root_node_id}' not found in graph."}

        # Build PROV document
        prov_doc = _build_prov_document(visited_nodes, visited_edges, profile)

        # Hash only canonical evidence content so repeated runs on identical
        # input graphs produce the same content hash.
        evidence_payload = {
            "root_node_id": root_node_id,
            "domain_profile": domain_profile_name,
            "nodes": visited_nodes,
            "edges": visited_edges,
            "traversal_path": path,
            "prov_document": prov_doc,
        }
        content_hash = _compute_hash(evidence_payload)
        bundle_id = f"urn:atlas:bundle:{uuid4().hex[:12]}"
        evidence = {
            "bundle_id": bundle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **evidence_payload,
        }

        # Detect compliance gaps
        gaps = _detect_gaps(visited_nodes, visited_edges, profile)

        result: Dict[str, Any] = {
            "valid": True,
            "bundle_id": bundle_id,
            "content_hash": content_hash,
            "traversal_path": path,
            "evidence_nodes": visited_nodes,
            "evidence_edges": visited_edges,
            "prov_document": prov_doc,
            "gaps_detected": gaps,
            "generated_at": evidence["timestamp"],
        }

        if mode == "report":
            result["narrative_report"] = _generate_narrative(
                visited_nodes, visited_edges, gaps, bundle_id, content_hash
            )

        gap_summary = f", {len(gaps)} compliance gap(s) detected" if gaps else ", no gaps"
        result["summary"] = (
            f"Traced {len(visited_nodes)} nodes, {len(visited_edges)} edges "
            f"from root '{root_node_id}'{gap_summary}. "
            f"Bundle hash: {content_hash[:16]}..."
        )

        return result

    async def _run_self_test(self) -> Dict[str, Any]:
        """Run built-in demo with the SMT manufacturing graph."""
        result = await self.invoke({
            "mode": "report",
            "root_node_id": "board-8842",
            "graph_data": DEMO_GRAPH,
            "domain_profile": "manufacturing",
        })
        repeat = await self.invoke({
            "mode": "trace",
            "root_node_id": "board-8842",
            "graph_data": DEMO_GRAPH,
            "domain_profile": "manufacturing",
        })
        result["self_test"] = True
        result["gap_count"] = len(result.get("gaps_detected", []))
        result["deterministic_hash"] = result.get("content_hash") == repeat.get("content_hash")
        return result


PLUGIN = TraceabilityComplianceWrapper()
