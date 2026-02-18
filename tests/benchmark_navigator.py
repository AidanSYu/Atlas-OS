"""Benchmark script for Navigator 2.0 optimization verification."""
import asyncio
import time
import sys
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent / "src" / "backend"
sys.path.append(str(backend_path))

from app.core.config import settings
from app.services.graph import GraphService
from app.services.llm import LLMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("benchmark")

async def test_graph_caching():
    """Test improvements in graph retrieval caching."""
    logger.info("=== Testing Graph Caching ===")
    
    graph_service = GraphService()
    project_id = "bench_project"
    
    # Run 1: Cold start (uncached)
    start = time.perf_counter()
    # Mocking or using actual DB if available. 
    # Since we can't easily mock the DB without complex setup, 
    # we'll try to call it and catch empty DB - improvements should still show in overhead
    try:
        G1 = await graph_service.get_networkx_subgraph(project_id=project_id)
        duration_cold = time.perf_counter() - start
        logger.info(f"Cold Graph Load: {duration_cold:.4f}s (Nodes: {G1.number_of_nodes()})")
        
        # Run 2: Cached
        start = time.perf_counter()
        G2 = await graph_service.get_networkx_subgraph(project_id=project_id)
        duration_warm = time.perf_counter() - start
        logger.info(f"Warm Graph Load: {duration_warm:.4f}s (Nodes: {G2.number_of_nodes()})")
        
        if duration_warm < duration_cold:
            logger.info(f"✅ Speedup: {duration_cold / duration_warm:.2f}x")
        else:
            logger.warning("⚠️ No speedup detected (possibly empty graph or DB overhead negligible)")
            
    except Exception as e:
        logger.error(f"Graph test failed (expected if no DB): {e}")

async def test_swam_imports():
    """Verify Swarm imports and configuration."""
    logger.info("\n=== Verifying Swarm Config ===")
    try:
        from app.services.swarm import _build_navigator_2_graph
        from app.services.rerank import get_rerank_service
        
        # Check settings
        logger.info(f"Reranking Enabled: {settings.ENABLE_RERANKING}")
        logger.info(f"Top N: {settings.RERANK_TOP_N}")
        logger.info(f"Graph TTL: {settings.GRAPH_CACHE_TTL}")
        
        # Check Rerank Service loading
        service = get_rerank_service()
        logger.info(f"Rerank Service initialized: {service}")
        
        logger.info("✅ Swarm configuration verified")
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
    except Exception as e:
        logger.error(f"❌ Configuration check failed: {e}")

async def main():
    logger.info("Starting Atlas Benchmarks...")
    
    await test_swam_imports()
    await test_graph_caching()
    
    logger.info("\nBenchmark Complete.")

if __name__ == "__main__":
    asyncio.run(main())
