from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import shutil
from pathlib import Path
from config import settings
from ingest import IngestionPipeline
from query_orchestrator import QueryOrchestrator
from document_store import DocumentStore
from knowledge_graph import KnowledgeGraph
from database import init_db

# Import working services from app structure
from app.services.chat import ChatService
from app.services.retrieval import RetrievalService

# Initialize database on startup
try:
    init_db()
    print("✓ Database initialized")
except Exception as e:
    print(f"Warning: Database initialization failed: {e}")

app = FastAPI(
    title="Atlas API - AI-Native Knowledge Layer",
    description="Scalable knowledge substrate for AI retrieval and reasoning",
    version="2.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances - Knowledge Layer
ingestion_pipeline = IngestionPipeline()
query_orchestrator = QueryOrchestrator()
doc_store = DocumentStore()
knowledge_graph = KnowledgeGraph()

# NEW: Working chat and retrieval services
chat_service = ChatService()
retrieval_service = RetrievalService()

# ============================================================
# PYDANTIC MODELS
# ============================================================

class ChatRequest(BaseModel):
    query: str
    query_type: Optional[str] = "general"  # general, document, relationship, search

class ChatResponse(BaseModel):
    answer: str
    reasoning: str
    citations: List[Dict[str, Any]]
    relationships: Optional[List[Dict[str, Any]]] = []
    context_sources: Dict[str, Any]

class FileInfo(BaseModel):
    filename: str
    doc_id: str
    status: str
    size_bytes: Optional[int] = None
    uploaded_at: Optional[str] = None
    processed_at: Optional[str] = None

class EntityInfo(BaseModel):
    id: str
    name: str
    type: str
    description: Optional[str]
    document_id: str

class RelationshipInfo(BaseModel):
    id: str
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    type: str
    context: Optional[str]

# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Atlas API - AI-Native Knowledge Layer",
        "version": "2.0.0",
        "architecture": {
            "vector_store": "Qdrant",
            "knowledge_graph": "PostgreSQL",
            "document_store": "PostgreSQL",
            "llm": "Ollama (local)"
        }
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check of all knowledge layers."""
    try:
        stats = query_orchestrator.get_stats()
        return {
            "status": "healthy",
            "layers": stats
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }

# ============================================================
# DOCUMENT INGESTION
# ============================================================

@app.post("/ingest", response_model=Dict[str, Any])
async def ingest_document(file: UploadFile = File(...)):
    """
    Upload and process a PDF document through the knowledge layer.
    
    Pipeline:
    1. Store document + chunks in PostgreSQL
    2. Embed chunks in Qdrant
    3. Extract entities and relationships for knowledge graph
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Save file
    file_path = Path(settings.UPLOAD_DIR) / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process through ingestion pipeline
        result = ingestion_pipeline.ingest_document(str(file_path), file.filename)
        
        return result
    
    except Exception as e:
        # Clean up on error
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

# ============================================================
# QUERY / CHAT
# ============================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Query the knowledge layer using hybrid RAG.
    
    The AI queries the living knowledge substrate:
    - Vector search (Qdrant) for semantic similarity
    - Graph expansion (PostgreSQL) for relationships
    - LLM synthesis (Ollama) for final answer
    """
    try:
        # Use working chat service instead of placeholder orchestrator
        response = chat_service.chat(request.query)
        
        # Ensure response is JSON serializable
        return ChatResponse(
            answer=response.get("answer", ""),
            reasoning=response.get("reasoning", ""),
            citations=[c for c in response.get("citations", []) if isinstance(c, dict)],
            relationships=[r for r in response.get("relationships", []) if isinstance(r, dict)],
            context_sources=response.get("context_sources", {})
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")

@app.get("/query/relationship")
async def query_relationship(entity1: str, entity2: str):
    """
    Find and explain how two entities are connected.
    
    Example: /query/relationship?entity1=benzene&entity2=catalyst
    """
    try:
        result = query_orchestrator.find_relationship(entity1, entity2)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Relationship query error: {str(e)}")

@app.get("/query/document/{doc_id}")
async def query_document(doc_id: str, question: str):
    """
    Answer questions about a specific document.
    
    Example: /query/document/abc-123?question=What is the main finding?
    """
    try:
        result = query_orchestrator.query_document(doc_id, question)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document query error: {str(e)}")

@app.get("/query/search")
async def search_documents(concept: str):
    """
    Find all documents mentioning a concept.
    
    Example: /query/search?concept=photocatalysis
    """
    try:
        result = query_orchestrator.find_documents_mentioning(concept)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

# ============================================================
# DOCUMENT MANAGEMENT
# ============================================================

@app.get("/files", response_model=List[FileInfo])
async def list_files(status: Optional[str] = None):
    """
    List all uploaded documents with their status.
    
    Status filter: pending, processing, completed, failed
    """
    try:
        documents = doc_store.list_documents(status=status, limit=100)
        
        return [
            FileInfo(
                filename=doc["filename"],
                doc_id=doc["id"],
                status=doc["status"],
                size_bytes=doc["file_size"],
                uploaded_at=doc["uploaded_at"],
                processed_at=doc["processed_at"]
            )
            for doc in documents
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

@app.get("/files/{doc_id}")
async def get_file(doc_id: str):
    """Stream a PDF file for viewing."""
    try:
        document = doc_store.get_document(doc_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        file_path = Path(document["file_path"])
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=document["filename"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")

@app.delete("/files/{doc_id}")
async def delete_file(doc_id: str):
    """
    Delete a document from all knowledge layers.
    
    Removes from:
    1. Vector store (Qdrant)
    2. Knowledge graph (PostgreSQL)
    3. Document store (PostgreSQL)
    4. Filesystem
    """
    try:
        # Delete from vector store
        ingestion_pipeline.vector_store.delete_document(doc_id)
        
        # Delete from document store (cascades to chunks and entities)
        success = doc_store.delete_document(doc_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"status": "success", "message": f"Deleted document {doc_id}"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion error: {str(e)}")

# ============================================================
# KNOWLEDGE GRAPH EXPLORATION
# ============================================================

@app.get("/entities", response_model=List[EntityInfo])
async def list_entities(
    entity_type: Optional[str] = None,
    document_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    List entities in the knowledge graph.
    
    Filters:
    - entity_type: chemical, experiment, measurement, concept, etc.
    - document_id: Entities from specific document
    """
    try:
        entities = knowledge_graph.find_entities(
            entity_type=entity_type,
            document_id=document_id,
            limit=limit
        )
        
        return [
            EntityInfo(
                id=e["id"],
                name=e["name"],
                type=e["type"],
                description=e["description"],
                document_id=e["document_id"]
            )
            for e in entities
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing entities: {str(e)}")

@app.get("/entities/{entity_id}/relationships", response_model=List[RelationshipInfo])
async def get_entity_relationships(entity_id: str, direction: str = "both"):
    """
    Get all relationships for an entity.
    
    Direction: outgoing, incoming, both
    """
    try:
        relationships = knowledge_graph.get_entity_relationships(
            entity_id,
            direction=direction
        )
        
        return [
            RelationshipInfo(
                id=r["id"],
                source_id=r["source_id"],
                source_name=r["source_name"],
                target_id=r["target_id"],
                target_name=r["target_name"],
                type=r["type"],
                context=r["context"]
            )
            for r in relationships
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting relationships: {str(e)}")

@app.get("/graph/types")
async def get_entity_types():
    """Get all entity types with counts."""
    try:
        types = knowledge_graph.get_entity_types()
        return {"entity_types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting types: {str(e)}")

# ============================================================
# STATISTICS & MONITORING
# ============================================================

@app.get("/debug/entities")
async def debug_entities(doc_id: Optional[str] = None, limit: int = 50):
    """Debug endpoint to check extracted entities."""
    try:
        entities = knowledge_graph.find_entities(
            document_id=doc_id,
            limit=limit
        )
        
        return {
            "total_entities": len(entities),
            "entities": entities
        }
    except Exception as e:
        return {
            "error": str(e),
            "total_entities": 0,
            "entities": []
        }

@app.get("/stats")
async def get_stats():
    """Get comprehensive knowledge layer statistics."""
    try:
        return query_orchestrator.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT
    )
