import requests

# Test with the other PDF
url = "http://localhost:8000/ingest"
pdf_path = "backend/data/uploads/Mao Dun - Creation tr G Yang-1.pdf"

try:
    with open(pdf_path, 'rb') as f:
        files = {'file': ('Mao_Dun_Creation.pdf', f, 'application/pdf')}
        response = requests.post(url, files=files)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")