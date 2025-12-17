from backend.agents.llm_client import call_ollama
import time

try:
    print("Testing Ollama connection...")
    start = time.time()
    response = call_ollama("Say hello", max_tokens=10, timeout=10)
    print(f"Ollama response: {response}")
    print(f"Time taken: {time.time() - start:.2f}s")
except Exception as e:
    print(f"Ollama call failed: {e}")
