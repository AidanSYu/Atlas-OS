"""
Exit-gate verification for Agent C6 — Candidate Generation & Screen endpoints.

Tests:
  1. generate_candidates (mock=True) yields valid SSE events with SMILES
  2. screen_candidates filters ethanol (MW=46.07) when constraint MW > 100
  3. screen_candidates passes aspirin (MW=180.16) when constraint MW > 100
  4. All SSE events follow "data: <json>\n\n" format

Run:
  cd src/backend
  python -m pytest ../../tests/test_c6_candidate_generation.py -v
"""
import asyncio
import json
import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))


def test_rdkit_property_computation():
    """Verify RDKit properties compute correctly for known molecules."""
    from app.services.candidate_generation import _compute_rdkit_properties

    # Ethanol: MW ~46.07
    ethanol = _compute_rdkit_properties("CCO")
    assert ethanol is not None, "Ethanol SMILES should be valid"
    assert 45 < ethanol["MW"] < 47, f"Ethanol MW should be ~46.07, got {ethanol['MW']}"

    # Aspirin: MW ~180.16
    aspirin = _compute_rdkit_properties("CC(=O)Oc1ccccc1C(=O)O")
    assert aspirin is not None, "Aspirin SMILES should be valid"
    assert 179 < aspirin["MW"] < 181, f"Aspirin MW should be ~180.16, got {aspirin['MW']}"

    # Invalid SMILES
    invalid = _compute_rdkit_properties("not_a_smiles")
    assert invalid is None, "Invalid SMILES should return None"


def test_constraint_checking():
    """Verify constraint logic for operators."""
    from app.services.candidate_generation import _check_constraint

    assert _check_constraint(46.07, {"operator": ">", "value": 100}) is False
    assert _check_constraint(180.16, {"operator": ">", "value": 100}) is True
    assert _check_constraint(400, {"operator": "<", "value": 500}) is True
    assert _check_constraint(600, {"operator": "<", "value": 500}) is False
    assert _check_constraint(3.0, {"operator": "between", "value": [2, 4]}) is True
    assert _check_constraint(5.0, {"operator": "between", "value": [2, 4]}) is False


def test_screen_ethanol_fails_mw_gt_100():
    """EXIT GATE: Ethanol (CCO, MW 46) must fail a MW > 100 constraint."""
    from app.services.candidate_generation import screen_candidates

    # We need a mock DiscoverySession — patch _load_session_params
    import app.services.candidate_generation as cg
    original = cg._load_session_params

    cg._load_session_params = lambda sid: {
        "objective": "test",
        "propertyConstraints": [{"property": "MW", "operator": ">", "value": 100}],
    }

    try:
        events = []

        async def _collect():
            async for chunk in screen_candidates(
                session_id="test-session",
                epoch_id="test-epoch",
                smiles_list=["CCO", "CC(=O)Oc1ccccc1C(=O)O"],
            ):
                events.append(chunk)

        asyncio.run(_collect())

        # Parse all events
        parsed = []
        for ev in events:
            assert ev.startswith("data: "), f"SSE event must start with 'data: ', got: {ev[:30]}"
            assert ev.endswith("\n\n"), f"SSE event must end with '\\n\\n'"
            data_str = ev[len("data: "):].rstrip("\n")
            parsed.append(json.loads(data_str))

        # Find the complete event
        complete_events = [e for e in parsed if e.get("type") == "complete"]
        assert len(complete_events) == 1, "Should have exactly one 'complete' event"

        surviving = complete_events[0]["surviving_candidates"]

        # Ethanol should NOT survive (MW ~46 < 100)
        ethanol_survived = any(c["renderData"] == "CCO" for c in surviving)
        assert not ethanol_survived, "Ethanol (MW ~46) must NOT survive MW > 100 constraint"

        # Aspirin SHOULD survive (MW ~180 > 100)
        aspirin_survived = any(c["renderData"] == "CC(=O)Oc1ccccc1C(=O)O" for c in surviving)
        assert aspirin_survived, "Aspirin (MW ~180) must survive MW > 100 constraint"

        # Verify CandidateArtifact shape
        aspirin_candidate = [c for c in surviving if c["renderData"] == "CC(=O)Oc1ccccc1C(=O)O"][0]
        assert "id" in aspirin_candidate
        assert aspirin_candidate["status"] == "pending"
        assert aspirin_candidate["renderType"] == "molecule_2d"
        assert isinstance(aspirin_candidate["properties"], list)
        assert len(aspirin_candidate["properties"]) > 0
        assert aspirin_candidate["score"] > 0
        assert aspirin_candidate["rank"] == 1

        print("  EXIT GATE PASSED: Ethanol correctly filtered, Aspirin survived")

    finally:
        cg._load_session_params = original


def test_generate_mock_sse_format():
    """Verify generate_candidates(mock=True) yields valid SSE events."""
    from app.services.candidate_generation import generate_candidates
    import app.services.candidate_generation as cg

    original = cg._load_session_params
    cg._load_session_params = lambda sid: {
        "objective": "EGFR inhibition test",
        "propertyConstraints": [],
    }

    try:
        events = []

        async def _collect():
            async for chunk in generate_candidates(
                session_id="test-session",
                epoch_id="test-epoch",
                mock=True,
            ):
                events.append(chunk)

        asyncio.run(_collect())

        # All events must be valid SSE format
        for ev in events:
            assert ev.startswith("data: "), f"Must start with 'data: '"
            assert ev.endswith("\n\n"), f"Must end with '\\n\\n'"

        # Parse and verify
        parsed = [json.loads(ev[len("data: "):].rstrip("\n")) for ev in events]
        types = [e["type"] for e in parsed]

        assert "progress" in types, "Should have progress events"
        assert "candidates" in types, "Should have candidates event"
        assert "complete" in types, "Should have complete event"

        # Candidates event should have non-empty smiles array
        candidates_event = [e for e in parsed if e["type"] == "candidates"][0]
        assert len(candidates_event["smiles"]) > 0, "Mock should return at least 1 SMILES"

        print("  EXIT GATE PASSED: Mock generate yields valid SSE events")

    finally:
        cg._load_session_params = original


if __name__ == "__main__":
    print("Running C6 exit-gate tests...\n")

    print("[1] RDKit property computation")
    test_rdkit_property_computation()
    print("  PASSED\n")

    print("[2] Constraint checking")
    test_constraint_checking()
    print("  PASSED\n")

    print("[3] Ethanol MW > 100 filter")
    test_screen_ethanol_fails_mw_gt_100()
    print()

    print("[4] Mock generate SSE format")
    test_generate_mock_sse_format()
    print()

    print("All C6 exit-gate tests PASSED.")
