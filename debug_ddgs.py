from duckduckgo_search import DDGS
import json

try:
    print("Testing DDGS...")
    results = list(DDGS().text("aspirin mechanism", max_results=5))
    print(f"Results found: {len(results)}")
    if len(results) > 0:
        print(f"First result: {results[0]}")
except Exception as e:
    print(f"DDGS failed: {e}")
    import traceback
    traceback.print_exc()
