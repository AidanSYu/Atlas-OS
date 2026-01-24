from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import shutil
from pathlib import Path
from neo4j import GraphDatabase
from config import settings
from ingest import DocumentProcessor
from librarian import LibrarianAgent

app = FastAPI(
    title="Atlas API",
    description="Scientific Knowledge Engine Backend",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
doc_processor = DocumentProcessor()
librarian = LibrarianAgent()
neo4j_driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

# Pydantic Models
class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]]
    context_used: Dict[str, Any]

class FileInfo(BaseModel):
    filename: str
    status: str
    size_bytes: Optional[int] = None
    indexed_at: Optional[str] = None

class NodeUpdate(BaseModel):
    node_id: str
    properties: Dict[str, Any]

class RelationshipCreate(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    properties: Optional[Dict[str, Any]] = {}

class GraphNode(BaseModel):
    id: str
    labels: List[str]
    properties: Dict[str, Any]

class GraphRelationship(BaseModel):
    id: str
    type: str
    source: str
    target: str
    properties: Dict[str, Any]

# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Atlas API",
        "version": "1.0.0"
    }

@app.post("/ingest", response_model=Dict[str, Any])
async def ingest_document(file: UploadFile = File(...)):
    """
    Upload and index a PDF document.
    
    Steps:
    1. Save PDF to local storage
    2. Extract and embed chunks into ChromaDB
    3. Extract entities and sync to Neo4j
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Save file
    file_path = Path(settings.UPLOAD_DIR) / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process document
        result = doc_processor.process_document(str(file_path), file.filename)
        
        return result
    
    except Exception as e:
        # Clean up on error
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat_with_librarian(request: ChatRequest):
    """
    Chat with the Librarian AI agent.
    
    Features:
    - Hybrid RAG (Vector + Graph) search
    - Automatic citation generation
    - Intelligent query routing
    """
    try:
        response = librarian.chat(request.query)
        return ChatResponse(**response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@app.get("/files", response_model=List[FileInfo])
async def list_files():
    """
    List all uploaded files with their status.
    """
    try:
        # Get files from Neo4j
        files_db = librarian.list_files()
        
        # Enhance with filesystem info
        result = []
        for file_info in files_db:
            file_path = Path(settings.UPLOAD_DIR) / file_info['name']
            size = file_path.stat().st_size if file_path.exists() else None
            
            result.append(FileInfo(
                filename=file_info['name'],
                status=file_info['status'],
                size_bytes=size,
                indexed_at=str(file_info.get('indexed_at', ''))
            ))
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

@app.get("/files/{filename}")
async def get_file(filename: str):
    """
    Stream a PDF file for viewing.
    """
    file_path = Path(settings.UPLOAD_DIR) / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename
    )

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """
    Delete a file from the system.
    
    Actions:
    1. Remove from ChromaDB
    2. Mark as archived in Neo4j
    3. Delete physical file
    """
    file_path = Path(settings.UPLOAD_DIR) / filename
    
    try:
        # Remove from databases
        doc_processor.delete_document(filename)
        
        # Delete physical file
        if file_path.exists():
            file_path.unlink()
        
        return {"status": "success", "message": f"Deleted {filename}"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion error: {str(e)}")

@app.post("/files/{filename}/reindex")
async def reindex_file(filename: str):
    """
    Re-index an existing file.
    """
    file_path = Path(settings.UPLOAD_DIR) / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        # Delete old data
        doc_processor.delete_document(filename)
        
        # Re-process
        result = doc_processor.process_document(str(file_path), filename)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-indexing error: {str(e)}")

# Graph Management Endpoints

@app.get("/graph", response_model=Dict[str, Any])
async def get_graph(
    limit: int = Query(100, ge=1, le=500),
    node_type: Optional[str] = None
):
    """
    Get graph data for visualization.
    """
    with neo4j_driver.session() as session:
        # Build query
        if node_type:
            query = f"""
            MATCH (n:{node_type})
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN n, r, m
            LIMIT $limit
            """
        else:
            query = """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN n, r, m
            LIMIT $limit
            """
        
        result = session.run(query, limit=limit)
        
        nodes = {}
        relationships = []
        
        for record in result:
            # Process source node
            n = record.get('n')
            if n:
                node_id = str(n.element_id)
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "labels": list(n.labels),
                        "properties": dict(n)
                    }
            
            # Process target node
            m = record.get('m')
            if m:
                node_id = str(m.element_id)
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "labels": list(m.labels),
                        "properties": dict(m)
                    }
            
            # Process relationship
            r = record.get('r')
            if r:
                relationships.append({
                    "id": str(r.element_id),
                    "type": r.type,
                    "source": str(n.element_id),
                    "target": str(m.element_id),
                    "properties": dict(r)
                })
        
        return {
            "nodes": list(nodes.values()),
            "relationships": relationships
        }

@app.put("/graph/nodes/{node_id}")
async def update_node(node_id: str, update: NodeUpdate):
    """
    Update node properties.
    """
    with neo4j_driver.session() as session:
        # Build SET clause
        set_clauses = [f"n.{key} = ${key}" for key in update.properties.keys()]
        query = f"""
        MATCH (n)
        WHERE elementId(n) = $node_id
        SET {', '.join(set_clauses)}
        RETURN n
        """
        
        try:
            result = session.run(query, node_id=node_id, **update.properties)
            record = result.single()
            
            if not record:
                raise HTTPException(status_code=404, detail="Node not found")
            
            node = record['n']
            return {
                "id": str(node.element_id),
                "labels": list(node.labels),
                "properties": dict(node)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")

@app.post("/graph/relationships")
async def create_relationship(rel: RelationshipCreate):
    """
    Create a new relationship between nodes.
    """
    with neo4j_driver.session() as session:
        query = f"""
        MATCH (a), (b)
        WHERE elementId(a) = $source_id AND elementId(b) = $target_id
        CREATE (a)-[r:{rel.relationship_type}]->(b)
        SET r += $properties
        RETURN r, a, b
        """
        
        try:
            result = session.run(
                query,
                source_id=rel.source_id,
                target_id=rel.target_id,
                properties=rel.properties
            )
            record = result.single()
            
            if not record:
                raise HTTPException(status_code=404, detail="Source or target node not found")
            
            r = record['r']
            a = record['a']
            b = record['b']
            
            return {
                "relationship": {
                    "id": str(r.element_id),
                    "type": r.type,
                    "source": str(a.element_id),
                    "target": str(b.element_id),
                    "properties": dict(r)
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Creation error: {str(e)}")

@app.delete("/graph/nodes/{node_id}")
async def delete_node(node_id: str):
    """
    Delete a node and its relationships.
    """
    with neo4j_driver.session() as session:
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        DETACH DELETE n
        """
        
        try:
            session.run(query, node_id=node_id)
            return {"status": "success", "message": f"Deleted node {node_id}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Deletion error: {str(e)}")

@app.delete("/graph/relationships/{rel_id}")
async def delete_relationship(rel_id: str):
    """
    Delete a relationship.
    """
    with neo4j_driver.session() as session:
        query = """
        MATCH ()-[r]->()
        WHERE elementId(r) = $rel_id
        DELETE r
        """
        
        try:
            session.run(query, rel_id=rel_id)
            return {"status": "success", "message": f"Deleted relationship {rel_id}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Deletion error: {str(e)}")

# Cleanup on shutdown
@app.on_event("shutdown")
def shutdown_event():
    """Clean up resources on shutdown."""
    doc_processor.close()
    librarian.close()
    neo4j_driver.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT
    )
