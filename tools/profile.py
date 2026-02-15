import sys
import os
import cProfile
import pstats

# Append ./backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

def profile_rag():
    print("Starting RAG pipeline profiling...")
    
    # Placeholder for actual RAG pipeline import and execution
    # from backend.app.services.retrieval import RetrievalService
    
    print("Running dummy search query via RetrievalService...")
    # service = RetrievalService()
    # service.search("dummy query")
    
    print("Profiling complete.")

if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()
    
    profile_rag()
    
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumtime')
    stats.print_stats()
