import requests

# Test the upload endpoint
url = "http://localhost:8000/ingest"
files = {'file': ('test.txt', 'This is a test document with some entities like benzene and catalyst.', 'text/plain')}

try:
    response = requests.post(url, files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")