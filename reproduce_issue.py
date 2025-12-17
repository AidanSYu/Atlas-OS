import requests
import json

try:
    response = requests.post(
        "http://127.0.0.1:8000/api/research/chat",
        json={"message": "What is the mechanism of aspirin?", "disease_context": "pain"},
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
