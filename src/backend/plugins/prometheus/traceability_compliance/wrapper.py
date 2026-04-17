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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
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
    """Build PROV document using the W3C prov Python library.

    Each PROV-DM type has its own constructor signature:
      - entity(identifier, attributes)
      - activity(identifier, startTime, endTime, attributes)
      - agent(identifier, attributes)
    Activities get `start`/`end` promoted out of metadata into positional args.
    """
    doc = prov_model.ProvDocument()
    doc.set_default_namespace("urn:atlas:prov:")

    refs: Dict[str, Any] = {}

    for node in nodes:
        node_id = node["id"]
        node_type = node.get("type", "Entity")
        prov_type = _resolve_prov_type(node_type, profile)
        attrs = dict(node.get("metadata", {}))
        attrs["prov:type"] = node_type

        if prov_type == "Activity":
            start = attrs.pop("start", None)
            end = attrs.pop("end", None)
            refs[node_id] = doc.activity(node_id, start, end, attrs)
        elif prov_type == "Agent":
            refs[node_id] = doc.agent(node_id, attrs)
        else:  # Entity (default)
            refs[node_id] = doc.entity(node_id, attrs)

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
) -> Tuple[List[Dict], List[Dict], List[str]]:
    """Bidirectional BFS from root_id using Rustworkx.

    Traceability walks must follow edges in *both* directions: an activity is
    upstream of the entity it generates, but downstream of the agent that
    performed it. We model the input as a directed graph (to preserve relation
    semantics when emitting PROV) but walk it ignoring direction.

    Returns (visited_nodes, visited_edges, traversal_path).
    """
    import rustworkx as rx

    graph = rx.PyDiGraph(multigraph=True)
    id_to_idx: Dict[str, int] = {}
    for node in nodes:
        id_to_idx[node["id"]] = graph.add_node(node)

    for edge in edges:
        src_id = edge.get("source")
        tgt_id = edge.get("target")
        if src_id in id_to_idx and tgt_id in id_to_idx:
            graph.add_edge(id_to_idx[src_id], id_to_idx[tgt_id], edge)

    if root_id not in id_to_idx:
        return [], [], []

    root_idx = id_to_idx[root_id]
    visited_node_idx: List[int] = []
    visited_edge_keys: set = set()
    visited_edges: List[Dict] = []
    depth: Dict[int, int] = {root_idx: 0}
    order: List[int] = [root_idx]
    cursor = 0

    while cursor < len(order):
        current = order[cursor]
        cursor += 1
        visited_node_idx.append(current)
        current_depth = depth[current]
        if current_depth >= max_depth:
            continue

        # Walk both directions — upstream (in_edges) and downstream (out_edges).
        for nbr_idx, edge_payload in (
            [(t, d) for _, t, d in graph.out_edges(current)]
            + [(s, d) for s, _, d in graph.in_edges(current)]
        ):
            edge_key = (
                min(current, nbr_idx),
                max(current, nbr_idx),
                edge_payload.get("id")
                or f"{edge_payload.get('source')}->{edge_payload.get('target')}",
            )
            if edge_key in visited_edge_keys:
                continue
            visited_edge_keys.add(edge_key)
            visited_edges.append(edge_payload)

            if nbr_idx not in depth:
                depth[nbr_idx] = current_depth + 1
                order.append(nbr_idx)

    visited_nodes = [graph.get_node_data(idx) for idx in visited_node_idx]
    path = [graph.get_node_data(idx)["id"] for idx in visited_node_idx]
    return visited_nodes, visited_edges, path


_CAL_DATE_MAX_AGE_DAYS = 365


def _parse_iso_date(value: Any) -> Optional[datetime]:
    """Best-effort parse of an ISO-8601 date/time string. Returns None on failure."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:10])  # try date-only slice
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _detect_gaps(nodes: List[Dict], edges: List[Dict], profile: Dict[str, str]) -> List[Dict]:
    """Detect compliance gaps across W3C PROV and common manufacturing-audit rules.

    Rule set:
      - missing_agent: activity with no associated agent (HIGH)
      - missing_provenance: entity without a generating activity or derivation source (MEDIUM)
      - unsigned_step: activity whose associated agents lack a `cert` or `signed_by` attribute (MEDIUM)
      - expired_calibration: equipment-class agent with `cal_date` older than one year (HIGH)
      - missing_timestamp: activity without any `start` or `end` timestamp (LOW)
    """
    gaps: List[Dict] = []
    node_map = {n["id"]: n for n in nodes}

    activities = {nid for nid, n in node_map.items()
                  if _resolve_prov_type(n.get("type", ""), profile) == "Activity"}
    agents = {nid for nid, n in node_map.items()
              if _resolve_prov_type(n.get("type", ""), profile) == "Agent"}
    entities = {nid for nid, n in node_map.items()
                if _resolve_prov_type(n.get("type", ""), profile) == "Entity"}

    # activity -> list of agent ids it was associated with
    activity_agents: Dict[str, List[str]] = {}
    for e in edges:
        if e.get("relation") == "wasAssociatedWith":
            activity_agents.setdefault(e["source"], []).append(e["target"])

    # Rule 1: missing_agent
    for act_id in activities:
        if act_id not in activity_agents:
            gaps.append({
                "type": "missing_agent",
                "node_id": act_id,
                "severity": "HIGH",
                "description": f"Activity '{act_id}' has no associated agent (operator/equipment).",
            })

    # Rule 2: missing_provenance
    entities_with_generation = {e["source"] for e in edges if e.get("relation") == "wasGeneratedBy"}
    for ent_id in entities:
        if ent_id in entities_with_generation:
            continue
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

    # Rule 3: unsigned_step — at least one associated agent must carry a credential.
    for act_id, associated in activity_agents.items():
        credentialed = False
        for agent_id in associated:
            agent_node = node_map.get(agent_id) or {}
            meta = agent_node.get("metadata", {}) or {}
            if meta.get("cert") or meta.get("signed_by") or meta.get("signature"):
                credentialed = True
                break
        if not credentialed and associated:
            gaps.append({
                "type": "unsigned_step",
                "node_id": act_id,
                "severity": "MEDIUM",
                "description": (
                    f"Activity '{act_id}' has agents but none carry a certification, "
                    f"signature, or signed_by attribute."
                ),
            })

    # Rule 4: expired_calibration — equipment-class agents with an old cal_date.
    now = datetime.now(timezone.utc)
    for agent_id in agents:
        agent_node = node_map[agent_id]
        meta = agent_node.get("metadata", {}) or {}
        cal_date = meta.get("cal_date") or meta.get("calibration_date")
        parsed = _parse_iso_date(cal_date)
        if parsed is None:
            continue
        age = now - parsed
        if age > timedelta(days=_CAL_DATE_MAX_AGE_DAYS):
            gaps.append({
                "type": "expired_calibration",
                "node_id": agent_id,
                "severity": "HIGH",
                "description": (
                    f"Agent '{agent_id}' calibration ({cal_date}) is {age.days} days old, "
                    f"exceeding the {_CAL_DATE_MAX_AGE_DAYS}-day limit."
                ),
            })

    # Rule 5: missing_timestamp
    for act_id in activities:
        meta = node_map[act_id].get("metadata", {}) or {}
        if not meta.get("start") and not meta.get("end"):
            gaps.append({
                "type": "missing_timestamp",
                "node_id": act_id,
                "severity": "LOW",
                "description": f"Activity '{act_id}' has no start or end timestamp recorded.",
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
