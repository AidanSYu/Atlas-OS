
import asyncio
import json
import httpx
from app.core.config import settings

# Since we can't easily run the full FastAPI app in a script without blocking,
# we will unit test the generator if possible, or try to hit the running server if active.
# For this verify step, we'll try to import the service and run the generator directly.

async def test_streaming_generator():
    print("Testing streaming generator directly...")
    from app.services.swarm import run_swarm_query_streaming
    from app.services.graph import GraphService
    from app.services.llm import get_llm_service
    from qdrant_client import QdrantClient
    
    # Mock services or use real ones if available
    try:
        graph_service = GraphService()
        llm_service = get_llm_service()
        # Mock Qdrant client to avoid connection issues in test
        qdrant_client = QdrantClient(":memory:") 
        collection_name = settings.QDRANT_COLLECTION
        
        query = "What is the capital of France?" # SIMPLE query -> Librarian
        project_id = "test_project"
        session_id = "test_session"
        
        print(f"Running query: {query}")
        
        async for event_type, event_data in run_swarm_query_streaming(
            query, project_id, session_id, graph_service, llm_service, qdrant_client, collection_name
        ):
            print(f"Event: {event_type}")
            # print(f"Data: {json.dumps(event_data, indent=2)}")
            
            if event_type == "complete":
                print("Stream complete!")
                print("Result:", event_data.get("hypothesis"))
                return True
                
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False

if __name__ == "__main__":
    # Ensure env vars are set if needed
    import os
    os.environ["ATLAS_N_CTX"] = "2048"
    
    try:
        asyncio.run(test_streaming_generator())
    except KeyboardInterrupt:
        pass
