try:
    from backend.agents.researcher import ResearcherAgent
    print("Initializing ResearcherAgent...")
    agent = ResearcherAgent()
    print("Testing _search_web with Google...")
    results = agent._search_web("aspirin mechanism", num=3)
    print(f"Results found: {len(results)}")
    for r in results:
        print(f" - {r.get('title')} ({r.get('url')})")
        
except Exception as e:
    print(f"Verification failed: {e}")
    import traceback
    traceback.print_exc()
