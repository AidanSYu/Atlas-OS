
import sys
import os
import asyncio
import logging

# Add src/backend to path so we can import app
sys.path.append(os.getcwd())

from app.services.llm import LLMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify():
    logger.info("Initializing LLMService (with lock fix)...")
    service = LLMService.get_instance()
    
    # Force load embedder
    await service.embed("warmup")
    
    logger.info("Testing batch embedding (simulating ingestion)...")
    
    # Specific lengths that caused issues
    texts = [
        "Short text.",
        "A" * 100,
        "A" * 500,
        "A" * 640,
        "A" * 700,
        "A" * 1000,
        "search_document: " + "A" * 640,
    ] * 5 # Repeat to make a larger batch
    
    try:
        embeddings = await service.embed_batch(texts)
        logger.info(f"Successfully generated {len(embeddings)} embeddings.")
        logger.info(f"Embedding shape: {len(embeddings[0])} dimensions.")
        logger.info("Fix verified: No tensor mismatch crash.")
    except Exception as e:
        logger.error(f"Verification FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify())
