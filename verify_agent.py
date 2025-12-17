try:
    from backend.agents.researcher import ResearcherAgent
    print("Import successful")
    
    agent = ResearcherAgent()
    print("Initialization successful")
    
    print("Testing search...")
    results = agent._search_web("test query", num=1)
    print(f"Search results: {len(results)}")
    
    print("Testing chat logic (mocking llm)...")
    # We won't call call_ollama to avoid hanging, just check if method exists
    print(f"Has professional_chat: {hasattr(agent, 'professional_chat')}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
