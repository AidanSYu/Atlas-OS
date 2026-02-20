
# Fix path for imports
import sys
import os
sys.path.append(os.path.abspath("src/backend"))

import asyncio
import logging
from app.services.graph import GraphService
from app.services.llm import get_llm_service
from app.services.swarm import run_swarm_query
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

async def test_run_swarm():
    try:
        print("Initializing services...")
        graph_service = GraphService()
        llm_service = get_llm_service()
        
        # Initialize default model if needed
        if not llm_service.active_model_name:
            print("Loading default model...")
            await llm_service.initialize_default_model()

        query = "What is the capital of France?"
        project_id = "test_debug_project"
        
        print(f"Running query: {query}")
        result = await run_swarm_query(
            query=query,
            project_id=project_id,
            graph_service=graph_service,
        )
        print("Result:", result)
        
    except Exception as e:
        logger.exception("Error running swarm query")

if __name__ == "__main__":
    asyncio.run(test_run_swarm())
