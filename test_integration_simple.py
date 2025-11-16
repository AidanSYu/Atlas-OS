#!/usr/bin/env python
"""Quick integration test for Drug Development Agent system."""

import sys
from pathlib import Path

backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

print("\n" + "=" * 60)
print("BACKEND + FRONTEND INTEGRATION TEST")
print("=" * 60)

# Test 1: Imports
print("\n[1/7] Testing imports...")
try:
    from agents.researcher import ResearcherAgent
    from agents.retrosynthesis import RetrosynthesisEngine, HuggingFaceChemLLM
    from agents.manufacturer import ManufacturabilityAgent
    print("    PASS: All agent imports successful")
    test1 = True
except Exception as e:
    print(f"    FAIL: {e}")
    test1 = False

# Test 2: Researcher Agent
print("\n[2/7] Testing Researcher Agent...")
try:
    researcher = ResearcherAgent()
    assert hasattr(researcher, 'generate_pathways')
    assert hasattr(researcher, 'deep_analyze_pathway')
    print("    PASS: ResearcherAgent initialized with methods")
    test2 = True
except Exception as e:
    print(f"    FAIL: {e}")
    test2 = False

# Test 3: Retrosynthesis Engine
print("\n[3/7] Testing Retrosynthesis Engine...")
try:
    engine = RetrosynthesisEngine()
    assert hasattr(engine, 'retrosynthesis_analysis')
    print("    PASS: RetrosynthesisEngine initialized")
    test3 = True
except Exception as e:
    print(f"    FAIL: {e}")
    test3 = False

# Test 4: Manufacturability Agent
print("\n[4/7] Testing Manufacturability Agent...")
try:
    mfg = ManufacturabilityAgent()
    assert hasattr(mfg, 'assess_scalability')
    print("    PASS: ManufacturabilityAgent initialized")
    test4 = True
except Exception as e:
    print(f"    FAIL: {e}")
    test4 = False

# Test 5: LLM Generation
print("\n[5/7] Testing LLM Generation (Retrosynthesis)...")
try:
    engine = RetrosynthesisEngine()
    result = engine.retrosynthesis_analysis(
        compound_name="Aspirin",
        smiles="CC(=O)Oc1ccccc1C(=O)O"
    )
    assert isinstance(result, dict)
    assert 'compound_name' in result
    print(f"    PASS: Retrosynthesis analysis returned dict with keys: {list(result.keys())[:3]}...")
    test5 = True
except Exception as e:
    print(f"    FAIL: {e}")
    test5 = False

# Test 6: Frontend Files
print("\n[6/7] Testing Frontend Structure...")
try:
    frontend_root = Path(__file__).parent / 'frontend'
    required_files = [
        'src/App.tsx',
        'src/main.tsx',
        'package.json',
        'vite.config.ts',
    ]
    
    all_exist = True
    for file in required_files:
        if not (frontend_root / file).exists():
            print(f"    MISSING: {file}")
            all_exist = False
    
    if all_exist:
        # Check App.tsx content
        app_tsx = frontend_root / 'src/App.tsx'
        content = app_tsx.read_text()
        
        required_content = [
            'useState',
            'Find Pathways',
            'Select & Analyze',
            'api<T>',
        ]
        
        for req in required_content:
            if req not in content:
                print(f"    MISSING in App.tsx: '{req}'")
                all_exist = False
    
    if all_exist:
        print("    PASS: All frontend files exist and contain required content")
        test6 = True
    else:
        test6 = False
except Exception as e:
    print(f"    FAIL: {e}")
    test6 = False

# Test 7: API Structure
print("\n[7/7] Testing FastAPI Setup...")
try:
    from app import app
    
    # Check that routes are defined
    routes = [route.path for route in app.routes]
    
    if '/api/health' in routes or any('health' in r for r in routes):
        print(f"    PASS: FastAPI app initialized with {len(routes)} routes")
        test7 = True
    else:
        print(f"    FAIL: Expected routes not found")
        test7 = False
except Exception as e:
    print(f"    FAIL: {e}")
    test7 = False

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)

results = [
    ("Agent Imports", test1),
    ("Researcher Agent", test2),
    ("Retrosynthesis Engine", test3),
    ("Manufacturability Agent", test4),
    ("LLM Generation", test5),
    ("Frontend Structure", test6),
    ("FastAPI Setup", test7),
]

passed = sum(1 for _, v in results if v)
total = len(results)

for name, passed_flag in results:
    status = "[PASS]" if passed_flag else "[FAIL]"
    print(f"  {status}: {name}")

print(f"\nTotal: {passed}/{total} tests passed")

if passed == total:
    print("\n[SUCCESS] ALL TESTS PASSED!")
    sys.exit(0)
else:
    print(f"\n[ERROR] {total - passed} test(s) failed")
    sys.exit(1)
