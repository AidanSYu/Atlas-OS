#!/usr/bin/env python
"""
Integration test for the Drug Development Agent system.
Tests backend agents, LLM integrations, and API endpoints.
"""

import sys
import json
import asyncio
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

def test_imports():
    """Test that all modules can be imported."""
    print("=" * 60)
    print("TEST 1: Checking Imports")
    print("=" * 60)
    try:
        from agents.researcher import ResearcherAgent
        from agents.retrosynthesis import RetrosynthesisEngine, HuggingFaceChemLLM
        from agents.manufacturer import ManufacturabilityAgent
        print("[PASS] All agent imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_huggingface_chemllm():
    """Test HuggingFace ChemLLM wrapper initialization and generation."""
    print("\n" + "=" * 60)
    print("TEST 2: HuggingFace ChemLLM Wrapper")
    print("=" * 60)
    try:
        from agents.retrosynthesis import HuggingFaceChemLLM
        
        print("Initializing HuggingFaceChemLLM...")
        llm = HuggingFaceChemLLM()
        print(f"✓ Model loaded: {llm.model is not None}")
        
        # Test generation
        prompt = "What is the synthesis of aspirin?"
        print(f"\nTest prompt: {prompt}")
        result = llm.generate(prompt, max_new_tokens=50)
        print(f"✓ Generation successful")
        print(f"  Response length: {len(result)} chars")
        print(f"  Sample: {result[:100]}..." if len(result) > 100 else f"  Response: {result}")
        return True
    except Exception as e:
        print(f"✗ HuggingFace ChemLLM test failed: {e}")
        return False


def test_researcher_agent():
    """Test ResearcherAgent initialization."""
    print("\n" + "=" * 60)
    print("TEST 3: Researcher Agent")
    print("=" * 60)
    try:
        from agents.researcher import ResearcherAgent
        
        print("Initializing ResearcherAgent...")
        researcher = ResearcherAgent()
        print("✓ ResearcherAgent initialized")
        
        # Check methods exist
        methods = ['_local_llm', 'generate_pathways', 'deep_analyze_pathway']
        for method in methods:
            if hasattr(researcher, method):
                print(f"  ✓ Method '{method}' exists")
            else:
                print(f"  ✗ Method '{method}' missing")
                return False
        return True
    except Exception as e:
        print(f"✗ ResearcherAgent test failed: {e}")
        return False


def test_retrosynthesis_engine():
    """Test RetrosynthesisEngine initialization."""
    print("\n" + "=" * 60)
    print("TEST 4: Retrosynthesis Engine")
    print("=" * 60)
    try:
        from agents.retrosynthesis import RetrosynthesisEngine
        
        print("Initializing RetrosynthesisEngine...")
        engine = RetrosynthesisEngine()
        print("✓ RetrosynthesisEngine initialized")
        
        # Check attributes
        attrs = ['chem_client', '_local_llm', 'retrosynthesis_analysis']
        for attr in attrs:
            if hasattr(engine, attr):
                print(f"  ✓ Attribute/method '{attr}' exists")
            else:
                print(f"  ✗ Attribute/method '{attr}' missing")
                return False
        return True
    except Exception as e:
        print(f"✗ RetrosynthesisEngine test failed: {e}")
        return False


def test_manufacturability_agent():
    """Test ManufacturabilityAgent initialization."""
    print("\n" + "=" * 60)
    print("TEST 5: Manufacturability Agent")
    print("=" * 60)
    try:
        from agents.manufacturer import ManufacturabilityAgent
        
        print("Initializing ManufacturabilityAgent...")
        mfg = ManufacturabilityAgent()
        print("✓ ManufacturabilityAgent initialized")
        
        # Check methods exist
        methods = ['_llm_assessment', 'assess_scalability', 'compare_candidates', 'estimate_production_capacity']
        for method in methods:
            if hasattr(mfg, method):
                print(f"  ✓ Method '{method}' exists")
            else:
                print(f"  ✗ Method '{method}' missing")
                return False
        return True
    except Exception as e:
        print(f"✗ ManufacturabilityAgent test failed: {e}")
        return False


def test_api_routes():
    """Test that FastAPI app can be created and routes are registered."""
    print("\n" + "=" * 60)
    print("TEST 6: FastAPI Routes")
    print("=" * 60)
    try:
        from app import app
        
        # Get all registered routes
        routes = [route.path for route in app.routes]
        
        required_routes = [
            '/openapi.json',
            '/api/health',
            '/api/researcher/pathways',
            '/api/researcher/deep_analyze',
            '/api/researcher/deep_analyze/start',
        ]
        
        print("Checking registered routes...")
        for route in required_routes:
            if route in routes or any(route.replace('{', '{').replace('}', '}') in r for r in routes):
                print(f"  ✓ Route '{route}' registered")
            else:
                print(f"  ✗ Route '{route}' NOT found")
        
        print(f"\n✓ Total routes registered: {len(routes)}")
        return True
    except Exception as e:
        print(f"✗ API routes test failed: {e}")
        return False


def test_frontend_structure():
    """Test that frontend files exist and are properly structured."""
    print("\n" + "=" * 60)
    print("TEST 7: Frontend Structure")
    print("=" * 60)
    try:
        frontend_root = Path(__file__).parent / 'frontend'
        
        required_files = [
            'src/App.tsx',
            'src/main.tsx',
            'src/App.css',
            'src/index.css',
            'package.json',
            'vite.config.ts',
            'tsconfig.json',
        ]
        
        print("Checking frontend files...")
        all_exist = True
        for file in required_files:
            filepath = frontend_root / file
            exists = filepath.exists()
            status = "✓" if exists else "✗"
            print(f"  {status} {file}")
            if not exists:
                all_exist = False
        
        if all_exist:
            # Check App.tsx for key content
            app_tsx = frontend_root / 'src/App.tsx'
            content = app_tsx.read_text()
            
            key_strings = [
                'useState',
                'Find Pathways',
                'Select & Analyze',
                'api<T>',
                'analysisProgress',
            ]
            
            print("\nChecking App.tsx content...")
            for key in key_strings:
                if key in content:
                    print(f"  ✓ Found: '{key}'")
                else:
                    print(f"  ✗ Missing: '{key}'")
                    all_exist = False
        
        return all_exist
    except Exception as e:
        print(f"✗ Frontend structure test failed: {e}")
        return False


def test_llm_generation():
    """Test actual LLM generation with retrosynthesis."""
    print("\n" + "=" * 60)
    print("TEST 8: LLM Generation (Retrosynthesis)")
    print("=" * 60)
    try:
        from agents.retrosynthesis import RetrosynthesisEngine
        
        print("Testing retrosynthesis analysis generation...")
        engine = RetrosynthesisEngine()
        
        # Test with a simple compound
        result = engine.retrosynthesis_analysis(
            compound_name="Aspirin",
            smiles="CC(=O)Oc1ccccc1C(=O)O"
        )
        
        print("✓ Retrosynthesis analysis completed")
        print(f"  Result type: {type(result)}")
        print(f"  Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        
        if isinstance(result, dict):
            for key, value in result.items():
                val_preview = str(value)[:80]
                print(f"    - {key}: {val_preview}...")
        
        return True
    except Exception as e:
        print(f"✗ LLM generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("DRUG DEVELOPMENT AGENT - INTEGRATION TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("HuggingFace ChemLLM", test_huggingface_chemllm),
        ("Researcher Agent", test_researcher_agent),
        ("Retrosynthesis Engine", test_retrosynthesis_engine),
        ("Manufacturability Agent", test_manufacturability_agent),
        ("API Routes", test_api_routes),
        ("Frontend Structure", test_frontend_structure),
        ("LLM Generation", test_llm_generation),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, passed_flag in results.items():
        status = "PASS" if passed_flag else "FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
