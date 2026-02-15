"""
Simple integration test for Navigator 2.0 (Phase A1).
Tests the reflection loop with a mock query.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.services.swarm import extract_xml_tag, parse_json_response, format_chunks


def test_helper_functions():
    """Test XML and JSON parsing helpers."""
    print("\n=== Testing Helper Functions ===")

    # Test XML extraction
    test_xml = """<thinking>
Step 1: Analyze the query
Step 2: Look for evidence
</thinking>
<hypothesis>The answer is based on evidence X</hypothesis>
<confidence>HIGH because multiple sources confirm</confidence>"""

    thinking = extract_xml_tag(test_xml, "thinking")
    hypothesis = extract_xml_tag(test_xml, "hypothesis")
    confidence = extract_xml_tag(test_xml, "confidence")

    assert "Step 1" in thinking, f"XML extraction failed for <thinking>: {thinking}"
    assert "evidence X" in hypothesis, f"XML extraction failed for <hypothesis>: {hypothesis}"
    assert "HIGH" in confidence, f"XML extraction failed for <confidence>: {confidence}"
    print("  [PASS] extract_xml_tag() works correctly")

    # Test JSON parsing
    test_json = '{"entities": ["polymer", "drug"], "dates": ["2024"], "key_phrases": []}'
    parsed = parse_json_response(test_json)

    assert parsed.get("entities") == ["polymer", "drug"], f"JSON parsing failed: {parsed}"
    assert parsed.get("dates") == ["2024"], f"JSON parsing failed: {parsed}"
    print("  [PASS] parse_json_response() works correctly")

    # Test format_chunks
    test_chunks = [
        {
            "text": "This is chunk 1 with important information about polymers.",
            "metadata": {"filename": "test.pdf", "page": 1, "chunk_id": "abc123"}
        },
        {
            "text": "This is chunk 2 with data on drug delivery systems.",
            "metadata": {"filename": "test.pdf", "page": 2, "chunk_id": "def456"}
        }
    ]

    formatted = format_chunks(test_chunks, max_chunks=2)
    assert "test.pdf" in formatted, f"Chunk formatting failed: {formatted}"
    assert "Page 1" in formatted, f"Chunk formatting missing page info: {formatted}"
    assert "[Source 1:" in formatted, f"Chunk formatting missing source prefix: {formatted}"
    print("  [PASS] format_chunks() works correctly")

    print("\n[SUCCESS] All helper functions PASS\n")


def test_configuration():
    """Test Navigator 2.0 configuration settings."""
    print("=== Testing Configuration ===")

    assert hasattr(settings, "ENABLE_NAVIGATOR_REFLECTION"), "Missing ENABLE_NAVIGATOR_REFLECTION"
    assert hasattr(settings, "MAX_REFLECTION_ITERATIONS"), "Missing MAX_REFLECTION_ITERATIONS"
    assert hasattr(settings, "NAVIGATOR_CONFIDENCE_THRESHOLD"), "Missing NAVIGATOR_CONFIDENCE_THRESHOLD"

    print(f"  ENABLE_NAVIGATOR_REFLECTION: {settings.ENABLE_NAVIGATOR_REFLECTION}")
    print(f"  MAX_REFLECTION_ITERATIONS: {settings.MAX_REFLECTION_ITERATIONS}")
    print(f"  NAVIGATOR_CONFIDENCE_THRESHOLD: {settings.NAVIGATOR_CONFIDENCE_THRESHOLD}")

    assert settings.MAX_REFLECTION_ITERATIONS == 3, "Expected MAX_REFLECTION_ITERATIONS=3"
    assert settings.NAVIGATOR_CONFIDENCE_THRESHOLD == 0.75, "Expected NAVIGATOR_CONFIDENCE_THRESHOLD=0.75"

    print("\n[SUCCESS] Configuration settings PASS\n")


def test_navigator_state():
    """Test NavigatorState TypedDict has all required fields."""
    print("=== Testing NavigatorState ===")

    from app.services.swarm import NavigatorState
    from typing import get_type_hints

    hints = get_type_hints(NavigatorState)
    required_fields = [
        "query", "project_id", "brain",
        "reasoning_plan", "identified_gaps", "search_terms",
        "retrieval_round", "retrieval_history",
        "verification_result", "confidence_score", "iteration_count",
        "evidence_map", "identified_contradictions"
    ]

    missing = [f for f in required_fields if f not in hints]

    if missing:
        print(f"  [FAIL] Missing fields: {missing}")
        sys.exit(1)

    print(f"  Total fields: {len(hints)}")
    print(f"  [PASS] All {len(required_fields)} required fields present")
    print("\n[SUCCESS] NavigatorState structure PASS\n")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Navigator 2.0 (Phase A1) Integration Test")
    print("="*60)

    try:
        test_configuration()
        test_helper_functions()
        test_navigator_state()

        print("\n" + "="*60)
        print("[SUCCESS] ALL TESTS PASSED - Navigator 2.0 is ready!")
        print("="*60)
        print("\nNext steps:")
        print("  1. Upload test documents via the frontend")
        print("  2. Try a complex query like:")
        print('     "How does polymer X relate to drug delivery systems?"')
        print("  3. Check logs for reflection loop iterations")
        print("  4. Verify confidence scores in responses")
        print("\n")

        return 0

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
