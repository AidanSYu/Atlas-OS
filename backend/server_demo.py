from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import os
from pathlib import Path

app = FastAPI(title="Atlas API - Demo Mode", version="1.0.0")

# CORS - Allow all for demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Simple in-memory storage
files_db = []
UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]]
    context_used: Dict[str, Any]

@app.get("/")
async def root():
    return {"status": "online", "service": "Atlas API (Demo Mode)", "version": "1.0.0"}

@app.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    file_path = UPLOAD_DIR / file.filename
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    files_db.append({
        "filename": file.filename,
        "status": "indexed",
        "size_bytes": len(content)
    })
    
    return {
        "status": "success",
        "filename": file.filename,
        "message": "File uploaded successfully (demo mode - no indexing)"
    }

@app.post("/chat")
async def chat_with_librarian(request: ChatRequest):
    query_lower = request.query.lower()
    
    if "files" in query_lower or "documents" in query_lower:
        if not files_db:
            answer = "No documents have been uploaded yet."
        else:
            file_list = "\n".join([f"- {f['filename']} (Status: {f['status']})" for f in files_db])
            answer = f"Here are the documents in the system:\n\n{file_list}"
        
        return ChatResponse(
            answer=answer,
            citations=[],
            context_used={"type": "file_list", "count": len(files_db)}
        )
    
    return ChatResponse(
        answer=f"Demo mode: I received your query '{request.query}'. For full functionality, please run the full backend with local Postgres + Qdrant (or set DB_BACKEND=sqlite and VECTOR_BACKEND=local).",
        citations=[],
        context_used={"type": "demo"}
    )

@app.get("/files")
async def list_files():
    return files_db

@app.get("/files/{filename}")
async def get_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, media_type="application/pdf", filename=filename)

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    global files_db
    file_path = UPLOAD_DIR / filename
    
    if file_path.exists():
        file_path.unlink()
    
    files_db = [f for f in files_db if f['filename'] != filename]
    
    return {"status": "success", "message": f"Deleted {filename}"}

@app.get("/graph")
async def get_graph():
    return {
        "nodes": [
            {"id": "demo1", "labels": ["Demo"], "properties": {"name": "Demo Mode Active"}},
            {"id": "demo2", "labels": ["Info"], "properties": {"name": "Install Neo4j for full features"}}
        ],
        "relationships": [
            {"id": "r1", "type": "INFO", "source": "demo1", "target": "demo2", "properties": {}}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 Starting Atlas Backend (Demo Mode)")
    print("="*60)
    print("⚠️  Running without Neo4j and ChromaDB")
    print("📝 Limited functionality - good for UI testing")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
