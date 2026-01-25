"""FastAPI route handlers."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import shutil

from app.services.chat import ChatService
from app.services.ingest import IngestionService
from app.services.document import DocumentService
from app.services.graph import GraphService
from app.core.config import settings

router = APIRouter()

# Initialize services lazily to avoid startup failures when dependencies are down
chat_service = None
ingestion_service = None
document_service = None
graph_service = None

def ensure_services():
    """Initialize services if not already created, handling dependency errors gracefully."""
    global chat_service, ingestion_service, document_service, graph_service
    if document_service is None:
        try:
            document_service = DocumentService()
        except Exception:
            document_service = None
    if graph_service is None:
        try:
            graph_service = GraphService()
        except Exception:
            graph_service = None
    if chat_service is None:
        try:
            chat_service = ChatService()
        except Exception:
            chat_service = None
    if ingestion_service is None:
        try:
            ingestion_service = IngestionService()
        except Exception:
            ingestion_service = None


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ChatRequest(BaseModel):
    query: str
    query_type: Optional[str] = "general"


class ChatResponse(BaseModel):
    answer: str
    reasoning: str
    citations: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    context_sources: Dict[str, Any]


# ============================================================
# ROUTES
# ============================================================

@router.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Atlas API - AI-Native Knowledge Layer",
        "version": "2.0.0",
        "architecture": {
            "vector_store": "Qdrant",
            "knowledge_graph": "PostgreSQL (Triple Store)",
            "llm": "Ollama (local)"
        }
    }


@router.get("/health")
async def health_check():
    """Health check of all services."""
    try:
        ensure_services()
        # Basic connectivity checks
        return {
            "status": "healthy",
            "services": {
                "api": "online",
                "qdrant": "available" if chat_service is not None else "unavailable",
                "postgres": "available" if document_service is not None else "unavailable",
                "ollama": "configured"  # runtime check done during calls
            }
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Query the knowledge layer using hybrid RAG.
    
    The AI queries the living knowledge substrate:
    - Vector search (Qdrant) for semantic similarity
    - Graph expansion (PostgreSQL) for relationships
    - LLM synthesis (Ollama) for final answer
    """
    ensure_services()
    
    # Robust error handling: attempt to re-initialize if service is None
    global chat_service
    if chat_service is None:
        try:
            chat_service = ChatService()
        except Exception as init_error:
            raise HTTPException(
                status_code=503, 
                detail=f"Chat service unavailable (vector store / Ollama not reachable): {str(init_error)}"
            )
    
    try:
        result = chat_service.chat(request.query)
        return ChatResponse(**result)
    except Exception as e:
        import traceback
        import logging
        logging.error(f"Chat error: {str(e)}")
        traceback.print_exc()
        # Return JSON error detail that frontend can read
        raise HTTPException(
            status_code=500, 
            detail=f"Query error: {str(e)}"
        )


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """
    Upload and process a PDF document through the knowledge layer.
    
    Pipeline:
    1. Store document + chunks in PostgreSQL
    2. Embed chunks in Qdrant (with node_id references)
    3. Extract entities and create graph nodes/edges
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Save file
    file_path = Path(settings.UPLOAD_DIR) / file.filename
    
    ensure_services()
    if ingestion_service is None:
        raise HTTPException(status_code=503, detail="Ingestion service unavailable (vector store / DB not reachable)")
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process through ingestion pipeline
        result = ingestion_service.ingest_document(str(file_path), file.filename)
        
        # Check if ingestion failed - atomic cleanup: delete file if ingestion failed
        if result.get("status") == "failed":
            # Delete the uploaded file immediately if ingestion failed
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as cleanup_error:
                    # Log but don't fail on cleanup errors
                    import logging
                    logging.error(f"Failed to cleanup file after ingestion failure: {cleanup_error}")
            raise HTTPException(status_code=500, detail=result.get("error", "Processing failed"))
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as cleanup_error:
                import logging
                logging.error(f"Failed to cleanup file after error: {cleanup_error}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.get("/files", response_model=List[Dict[str, Any]])
async def list_files(status: Optional[str] = None):
    """
    List all uploaded documents with their status.
    
    Status filter: pending, processing, completed, failed
    """
    ensure_services()
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service unavailable (DB not reachable)")
    try:
        documents = document_service.list_documents(status=status, limit=100)
        return documents
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


@router.get("/files/{doc_id}")
async def get_file(doc_id: str):
    """Stream a PDF file for viewing."""
    ensure_services()
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service unavailable (DB not reachable)")
    try:
        file_response = document_service.get_document_file(doc_id)
        
        if not file_response:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return file_response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")


@router.delete("/files/{doc_id}")
async def delete_file(doc_id: str):
    """
    Delete a document from all knowledge layers.
    
    Removes from:
    1. Vector store (Qdrant)
    2. Knowledge graph (PostgreSQL)
    3. Document store (PostgreSQL)
    4. Filesystem
    """
    ensure_services()
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service unavailable (DB not reachable)")
    try:
        success = document_service.delete_document(doc_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"status": "success", "message": f"Deleted document {doc_id}"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion error: {str(e)}")


@router.get("/entities", response_model=List[Dict[str, Any]])
async def list_entities(
    entity_type: Optional[str] = None,
    document_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    List nodes (entities) in the knowledge graph.
    
    Filters:
    - entity_type: Node label (e.g., "chemical", "experiment", "concept")
    - document_id: Nodes from specific document
    """
    ensure_services()
    if graph_service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable (DB not reachable)")
    try:
        nodes = graph_service.list_nodes(
            label=entity_type,
            document_id=document_id,
            limit=limit
        )
        return nodes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing entities: {str(e)}")


@router.get("/entities/{entity_id}/relationships", response_model=List[Dict[str, Any]])
async def get_entity_relationships(entity_id: str, direction: str = "both"):
    """
    Get all relationships for a node (entity).
    
    Direction: outgoing, incoming, both
    """
    ensure_services()
    if graph_service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable (DB not reachable)")
    try:
        relationships = graph_service.get_node_relationships(
            entity_id,
            direction=direction
        )
        return relationships
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting relationships: {str(e)}")


@router.get("/graph/types")
async def get_entity_types():
    """Get all node labels (types) with counts."""
    ensure_services()
    if graph_service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable (DB not reachable)")
    try:
        types = graph_service.get_node_types()
        return {"entity_types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting types: {str(e)}")


@router.get("/graph/full")
async def get_full_graph(document_id: Optional[str] = None):
    """
    Get complete graph (nodes + edges) in one request.
    Prevents graph 'explosion' by loading everything at once instead of lazy-loading edges.
    
    Query params:
    - document_id: Optional filter to get graph for specific document
    """
    ensure_services()
    if graph_service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable (DB not reachable)")
    try:
        result = graph_service.get_full_graph(document_id=document_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting full graph: {str(e)}")
