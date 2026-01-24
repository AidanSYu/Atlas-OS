import requests

# Test the upload endpoint with an existing PDF
url = "http://localhost:8000/ingest"
pdf_path = "backend/data/uploads/Assignment 3.pdf"

try:
    with open(pdf_path, 'rb') as f:
        files = {'file': ('Assignment 3.pdf', f, 'application/pdf')}
        response = requests.post(url, files=files)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")