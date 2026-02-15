import os
import sys
import httpx
from dotenv import load_dotenv

# Load .env
from pathlib import Path
root = Path(__file__).resolve().parent.parent.parent
env_path = root / "config" / ".env"
load_dotenv(env_path)

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip().strip('"').strip("'")
MINIMAX_KEY = os.getenv("MINIMAX_API_KEY", "").strip().strip('"').strip("'")

def test_deepseek():
    print("\nTesting DeepSeek API (Chat Completion)...")
    if not DEEPSEEK_KEY:
        print("FAIL: DEEPSEEK_API_KEY not found in .env")
        return

    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}"}
    data = {
        "model": "deepseek-reasoner",
        "messages": [{"role": "user", "content": "Ping"}],
        "max_tokens": 10
    }
    
    try:
        print(f"Sending request to {url}...")
        resp = httpx.post(url, headers=headers, json=data, timeout=30)
        
        if resp.status_code == 200:
            print("SUCCESS: DeepSeek R1 (deepseek-reasoner) is working.")
        elif resp.status_code == 401:
            print("FAIL: DeepSeek API key rejected (401 Unauthorized).")
            print(f"Response: {resp.text}")
        else:
            print(f"FAIL: DeepSeek returned unexpected status {resp.status_code}")
            print(resp.text)
            
    except Exception as e:
        print(f"ERROR: Could not connect to DeepSeek: {e}")

def test_minimax():
    print("\nTesting MiniMax API (via OpenAI compatible endpoint)...")
    if not MINIMAX_KEY:
        print("FAIL: MINIMAX_API_KEY not found in .env")
        return

    # Try International Endpoint (USD) first
    url_intl = "https://api.minimax.io/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MINIMAX_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "MiniMax-M2.5", 
        "messages": [{"role": "user", "content": "Ping"}],
        "max_tokens": 10
    }
    
    print(f"Trying International Endpoint: {url_intl} ...")
    try:
        resp = httpx.post(url_intl, headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            print("SUCCESS: MiniMax 2.5 is working (International Endpoint).")
            return "https://api.minimax.io/v1"
        else:
            print(f"International Endpoint Failed: {resp.status_code} - {resp.text}")
    except Exception as e:
         print(f"International Endpoint Error: {e}")

    # Try China Endpoint (RMB)
    url_cn = "https://api.minimax.chat/v1/chat/completions"
    print(f"\nTrying China Endpoint: {url_cn} ...")
    try:
        resp = httpx.post(url_cn, headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            print("SUCCESS: MiniMax 2.5 is working (China Endpoint).")
            return "https://api.minimax.chat/v1"
        else:
             print(f"China Endpoint Failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"China Endpoint Error: {e}")
    
    print("\nFAIL: Could not authenticate with either endpoint.")
    return None

if __name__ == "__main__":
    test_deepseek()
    test_minimax()
