import requests
import json
from typing import Optional

def call_ollama(prompt: str, model: str = "llama3.2:1b", max_tokens: int = 2048, timeout: int = 120) -> str:
    """
    Query the local Ollama server.
    
    Args:
        prompt: The prompt to send to the model.
        model: The model name to use (default: llama3.2:1b).
        max_tokens: Maximum number of tokens to predict.
        timeout: Request timeout in seconds.
        
    Returns:
        The text response from the model.
        
    Raises:
        RuntimeError: If Ollama is not running or returns an error.
    """
    try:
        url = "http://127.0.0.1:11434/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "num_predict": max_tokens,
        }
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        try:
            data = response.json()
            return data.get("response", "").strip()
        except json.JSONDecodeError:
            raise RuntimeError(f"Ollama returned invalid JSON. Status: {response.status_code}, Body: {response.text[:100]}")

    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if "Connection refused" in error_msg or "ConnectTimeout" in error_msg or "Max retries exceeded" in error_msg:
            raise RuntimeError(
                "Ollama is not running or unreachable.\n"
                "1. Install Ollama: https://ollama.ai\n"
                f"2. Pull the model: `ollama pull {model}`\n"
                "3. Start the server: `ollama serve`"
            )
        elif "Read timed out" in error_msg:
            raise RuntimeError(
                "Ollama request timed out. The model may be taking too long."
            )
        else:
            raise RuntimeError(f"Ollama HTTP error: {error_msg}")
