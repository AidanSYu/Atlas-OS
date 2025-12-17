from googlesearch import search

print("Testing advanced=True")
try:
    results = list(search("test", num_results=5, advanced=True))
    print(f"Results: {len(results)}")
except Exception as e:
    print(f"Advanced failed: {e}")

print("Testing advanced=False")
try:
    results = list(search("test", num_results=5, advanced=False))
    print(f"Results: {len(results)}")
    print(results)
except Exception as e:
    print(f"Basic failed: {e}")
