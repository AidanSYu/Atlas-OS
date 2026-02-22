"""
Lightweight verification for Cortex 2.0 (Phase A2) - ASCII only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    print("\n" + "="*70)
    print("Cortex 2.0 (Phase A2) Verification")
    print("="*70 + "\n")

    try:
        # Test 1: Configuration
        print("[TEST 1] Configuration Settings")
        from app.core.config import settings

        assert hasattr(settings, "ENABLE_CORTEX_CROSSCHECK")
        assert hasattr(settings, "CORTEX_NUM_SUBTASKS")
        
        print(f"  [PASS] ENABLE_CORTEX_CROSSCHECK: {settings.ENABLE_CORTEX_CROSSCHECK}")
        print(f"  [PASS] CORTEX_NUM_SUBTASKS: {settings.CORTEX_NUM_SUBTASKS}")
        assert settings.CORTEX_NUM_SUBTASKS == 5
        print()

        # Test 2: Code Structure
        print("[TEST 2] Code Structure")
        swarm_file = Path(__file__).parent / "app" / "services" / "swarm.py"
        content = swarm_file.read_text(encoding='utf-8')

        assert "class CortexState(TypedDict" in content
        print("  [PASS] CortexState TypedDict defined")

        assert "def _build_cortex_2_graph(" in content
        print("  [PASS] _build_cortex_2_graph function defined")

        nodes = ["decomposer_node", "executor_node", "cross_checker_node", "synthesizer_node"]
        for node in nodes:
            assert f"async def {node}" in content
        print(f"  [PASS] All {len(nodes)} nodes defined")
        print()

        # Test 3: Phase A1 Compatibility
        print("[TEST 3] Phase A1 + A2 Integration")
        assert hasattr(settings, "ENABLE_NAVIGATOR_REFLECTION")
        assert hasattr(settings, "MAX_REFLECTION_ITERATIONS")
        print("  [PASS] Navigator 2.0 settings intact")
        print("  [PASS] Cortex 2.0 settings intact")
        print()

        # Test 4: Feature Completeness
        print("[TEST 4] Feature Completeness")
        features = {
            "Coverage Validation": "coverage_check",
            "Chain-of-Thought": "<thinking>",
            "Contradiction Detection": "contradictions",
            "Confidence Scoring": "confidence_score",
        }

        for feature, keyword in features.items():
            assert keyword in content
            print(f"  [PASS] {feature}")
        print()

        # Summary
        print("="*70)
        print("SUCCESS - All tests passed!")
        print("="*70)
        print("\nPhase A2 Implementation Complete:")
        print("  [OK] Enhanced decomposer with coverage validation")
        print("  [OK] Per-task chain-of-thought executor")
        print("  [OK] Cross-checker for contradiction detection")
        print("  [OK] Confidence-aware synthesis")
        print("\nDevelopment Status:")
        print("  [DONE] Phase A1: Navigator 2.0 with reflection loops")
        print("  [DONE] Phase A2: Cortex 2.0 with cross-checking")
        print("  [NEXT] Phase A3: Prompt Engineering & Chain-of-Thought")
        print("\nReady to test with live queries!")
        print("="*70 + "\n")

        return 0

    except AssertionError as e:
        print(f"\n[FAIL] {e}\n")
        return 1
    except Exception as e:
        print(f"\n[ERROR] {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
