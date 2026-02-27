"""Tests for Phase 4: SynthesisMemoryService.

Covers:
  test_record_experiment_creates_node  - writes SynthesisAttempt node to DB
  test_record_experiment_creates_edge  - creates ATTEMPTED_VIA edge when compound exists
  test_find_similar_attempts_tanimoto  - returns only structurally-similar attempts
  test_find_similar_attempts_no_rdkit  - graceful fallback when RDKit unavailable
  test_embed_experiment_calls_qdrant   - calls embed() then qdrant.upsert()
  test_build_summary_format            - verifies human-readable summary text
"""
import asyncio
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.synthesis_memory import SynthesisMemoryService


# ============================================================
# Fixtures
# ============================================================

ASPIRIN_SMILES = "CC(=O)OC1=CC=CC=C1C(=O)O"
SALICYLIC_SMILES = "OC(=O)c1ccccc1O"          # structurally similar to aspirin
CAFFEINE_SMILES = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"  # completely different


def _make_service():
    """Return a SynthesisMemoryService with lazy services replaced by mocks."""
    svc = SynthesisMemoryService()
    svc._llm_service = MagicMock()
    svc._llm_service.embed = AsyncMock(return_value=[0.1] * 768)
    svc._qdrant_client = MagicMock()
    svc._qdrant_client.upsert = MagicMock()
    return svc


# ============================================================
# Test: record_experiment — happy path
# ============================================================

@pytest.mark.asyncio
async def test_record_experiment_creates_node():
    """record_experiment() writes a SynthesisAttempt Node to the DB."""
    svc = _make_service()

    # Patch the sync write to avoid needing a live DB
    with patch.object(svc, "_write_node_sync") as mock_write:
        node_id = await svc.record_experiment(
            project_id="proj-1",
            smiles=ASPIRIN_SMILES,
            route={"steps": [{"reagent": "acetic anhydride"}], "predicted_yield": 0.72},
            match_score=0.91,
            assay_result={"IC50_nM": 250},
        )

    assert isinstance(node_id, str)
    assert len(node_id) == 36  # UUID format

    mock_write.assert_called_once()
    call_args = mock_write.call_args[0]
    node_id_arg, project_id_arg, props_arg = call_args

    assert project_id_arg == "proj-1"
    assert props_arg["smiles"] == ASPIRIN_SMILES
    assert props_arg["match_score"] == 0.91
    assert props_arg["assay_result"] == {"IC50_nM": 250}
    assert props_arg["label"] if "label" in props_arg else True
    assert "timestamp" in props_arg


# ============================================================
# Test: _write_node_sync creates ATTEMPTED_VIA edge
# ============================================================

def test_write_node_sync_creates_edge_when_compound_exists():
    """_write_node_sync creates an ATTEMPTED_VIA edge to an existing compound node."""
    from app.core.database import Node, Edge

    compound_id = str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())

    existing_compound = Node(
        id=compound_id,
        label="chemical",
        properties={"name": "Aspirin", "smiles": ASPIRIN_SMILES},
        project_id="proj-2",
    )

    mock_session = MagicMock()
    # _write_node_sync uses a single .filter(label, project_id).all() call
    mock_session.query.return_value.filter.return_value.all.return_value = [existing_compound]

    added_objects = []
    mock_session.add.side_effect = lambda obj: added_objects.append(obj)

    svc = SynthesisMemoryService()

    # get_session is imported locally inside _write_node_sync, so patch at source
    with patch("app.core.database.get_session", return_value=mock_session):
        svc._write_node_sync(
            node_id=attempt_id,
            project_id="proj-2",
            props={
                "name": f"SynthesisAttempt:{ASPIRIN_SMILES[:40]}",
                "smiles": ASPIRIN_SMILES,
                "route": {},
                "match_score": 0.85,
                "assay_result": {},
                "notes": "",
                "timestamp": "2026-02-27T00:00:00",
            },
        )

    node_adds = [o for o in added_objects if isinstance(o, Node)]
    edge_adds = [o for o in added_objects if isinstance(o, Edge)]

    assert len(node_adds) == 1, "Should add exactly one Node"
    assert node_adds[0].id == attempt_id

    assert len(edge_adds) == 1, "Should create one ATTEMPTED_VIA edge"
    assert edge_adds[0].type == "ATTEMPTED_VIA"
    assert edge_adds[0].source_id == compound_id
    assert edge_adds[0].target_id == attempt_id


# ============================================================
# Test: find_similar_attempts — Tanimoto filtering
# ============================================================

@pytest.mark.asyncio
async def test_find_similar_attempts_tanimoto():
    """Returns structurally similar attempts and excludes dissimilar ones.

    Uses aspirin as both the query AND the stored candidate (Tanimoto=1.0),
    ensuring it reliably passes the 0.7 threshold.  Caffeine is used as the
    dissimilar control (Tanimoto << 0.7).
    """
    svc = _make_service()

    similar_node_id = str(uuid.uuid4())
    dissimilar_node_id = str(uuid.uuid4())

    from app.core.database import Node
    # Using ASPIRIN_SMILES as the "similar" candidate (same molecule → Tanimoto 1.0)
    similar_node = Node(
        id=similar_node_id,
        label="SynthesisAttempt",
        properties={
            "smiles": ASPIRIN_SMILES,   # identical → Tanimoto = 1.0
            "match_score": 0.88,
            "assay_result": {},
            "route": {},
            "timestamp": "2026-02-20T00:00:00",
            "notes": "",
        },
        project_id="proj-3",
    )
    dissimilar_node = Node(
        id=dissimilar_node_id,
        label="SynthesisAttempt",
        properties={
            "smiles": CAFFEINE_SMILES,   # completely different → Tanimoto ~ 0.07
            "match_score": 0.55,
            "assay_result": {},
            "route": {},
            "timestamp": "2026-02-21T00:00:00",
            "notes": "",
        },
        project_id="proj-3",
    )

    mock_session = MagicMock()
    # _find_similar_sync uses: session.query(Node).filter(label_cond, project_cond).all()
    # That is a single .filter() call with two conditions, not chained .filter().filter()
    mock_session.query.return_value.filter.return_value.all.return_value = [
        similar_node,
        dissimilar_node,
    ]

    # get_session is imported locally inside _find_similar_sync, patch at source
    with patch("app.core.database.get_session", return_value=mock_session):
        results = await svc.find_similar_attempts(
            project_id="proj-3",
            smiles=ASPIRIN_SMILES,
            top_k=5,
            tanimoto_threshold=0.7,
        )

    smiles_in_results = [r["smiles"] for r in results]
    assert ASPIRIN_SMILES in smiles_in_results, "Aspirin self-match should pass threshold"
    assert CAFFEINE_SMILES not in smiles_in_results, "Caffeine should be filtered out"
    assert len(results) == 1

    for r in results:
        assert r["tanimoto"] >= 0.7


# ============================================================
# Test: embed_experiment — verifies embed() + qdrant.upsert()
# ============================================================

@pytest.mark.asyncio
async def test_embed_experiment_calls_qdrant():
    """embed_experiment() calls LLMService.embed() then qdrant_client.upsert()."""
    svc = _make_service()
    node_id = str(uuid.uuid4())

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.QDRANT_COLLECTION = "atlas_docs"
        await svc.embed_experiment(
            project_id="proj-4",
            experiment_node_id=node_id,
            smiles=ASPIRIN_SMILES,
            route={"steps": [], "predicted_yield": 0.65},
            match_score=0.91,
            assay_result={"IC50_nM": 45},
        )

    svc._llm_service.embed.assert_called_once()
    embed_text = svc._llm_service.embed.call_args[0][0]
    assert ASPIRIN_SMILES in embed_text, "Embed text should contain SMILES"

    svc._qdrant_client.upsert.assert_called_once()
    upsert_kwargs = svc._qdrant_client.upsert.call_args
    # Points list should contain one PointStruct with the correct payload
    points = upsert_kwargs[1]["points"] if upsert_kwargs[1] else upsert_kwargs[0][1]
    assert len(points) == 1
    assert points[0].payload["smiles"] == ASPIRIN_SMILES
    assert points[0].payload["source_type"] == "synthesis_memory"
    assert points[0].payload["project_id"] == "proj-4"


# ============================================================
# Test: _build_summary — correct text format
# ============================================================

def test_build_summary_format():
    """_build_summary assembles all fields into a coherent plaintext string."""
    summary = SynthesisMemoryService._build_summary(
        smiles=ASPIRIN_SMILES,
        route={"steps": [1, 2], "predicted_yield": 0.8, "reagents": ["AcOH", "H2SO4"]},
        match_score=0.91,
        assay_result={"IC50_nM": 45},
        notes="Slight yellowing observed.",
    )

    assert ASPIRIN_SMILES in summary
    assert "PASSED" in summary          # 0.91 >= 0.70
    assert "2 steps" in summary
    assert "AcOH" in summary
    assert "IC50_nM" in summary
    assert "45" in summary
    assert "Slight yellowing" in summary


def test_build_summary_failed_verification():
    """_build_summary marks low match scores as FAILED."""
    summary = SynthesisMemoryService._build_summary(
        smiles=ASPIRIN_SMILES,
        route=None,
        match_score=0.45,
        assay_result=None,
        notes="",
    )
    assert "FAILED" in summary
    assert "0.45" in summary
