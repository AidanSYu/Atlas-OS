"""FastAPI route handlers for Atlas Sidecar API."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import shutil
import logging

from app.services.chat import ChatService
from app.services.ingest import IngestionService
from app.services.document import DocumentService
from app.services.graph import GraphService
from app.services.llm import get_llm_service
from app.core.config import settings

router = APIRouter()

# Services initialized lazily
chat_service = None
ingestion_service = None
document_service = None
graph_service = None

logger = logging.getLogger(__name__)


def ensure_services():
    """Initialize services - FATAL on failure."""
    global chat_service, ingestion_service, document_service, graph_service

    if document_service is None:
        document_service = DocumentService()
        logger.info("DocumentService initialized")
    if graph_service is None:
        graph_service = GraphService()
        logger.info("GraphService initialized")
    if chat_service is None:
        chat_service = ChatService()
        logger.info("ChatService initialized")
    if ingestion_service is None:
        ingestion_service = IngestionService()
        logger.info("IngestionService initialized")


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ChatRequest(BaseModel):
    query: str
    project_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    reasoning: str
    citations: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    context_sources: Dict[str, Any]


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: str


class SwarmRequest(BaseModel):
    project_id: str
    query: str


class SwarmResponse(BaseModel):
    brain_used: str  # "navigator" or "cortex"
    hypothesis: str
    evidence: List[Dict[str, Any]]
    reasoning_trace: List[str]
    status: str


class ModelLoadRequest(BaseModel):
    model_name: str


class ModelLoadResponse(BaseModel):
    active_model: Optional[str]
    model_type: str
    device: str
    gpu_layers: int
    fallback: bool


# ============================================================
# HEALTH / INFO
# ============================================================

@router.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Atlas API - Agentic RAG Knowledge Engine",
        "version": "2.0.0-sidecar",
        "architecture": {
            "database": "SQLite (embedded)",
            "vector_store": "Qdrant (embedded, in-process)",
            "knowledge_graph": "SQLite + NetworkX",
            "llm": "llama-cpp-python (bundled)",
            "swarm": "LangGraph Two-Brain (Navigator + Cortex)",
        },
    }


@router.get("/health")
async def health_check():
    """Lightweight health check - confirms the server is running.
    
    Does NOT initialize heavy ML services; that happens lazily on first
    real request.  Tauri's start_backend loop polls this endpoint.
    """
    return {
        "status": "healthy",
        "services": {
            "api": "online",
            "database": "sqlite",
            "vector_store": "qdrant_embedded",
            "llm": "bundled",
        },
    }


@router.get("/models")
async def list_models():
    """List bundled/available models in the models directory."""
    models_dir = Path(settings.MODELS_DIR)
    if not models_dir.exists():
        return {
            "models_dir": str(models_dir),
            "llm": [],
            "embeddings": [],
            "ner": [],
            "other": [],
            "message": "Models directory not found",
        }

    llm_models = [{"name": p.name, "path": str(p)} for p in sorted(models_dir.glob("*.gguf"))]
    embedding_models = [
        {"name": p.name, "path": str(p)}
        for p in sorted(models_dir.glob("nomic-embed-text*"))
        if p.is_dir()
    ]
    ner_models = [
        {"name": p.name, "path": str(p)}
        for p in sorted(models_dir.glob("gliner*"))
        if p.is_dir()
    ]
    known_paths = {
        *[m["path"] for m in llm_models],
        *[m["path"] for m in embedding_models],
        *[m["path"] for m in ner_models],
    }
    other_items = [
        {"name": p.name, "path": str(p)}
        for p in sorted(models_dir.iterdir())
        if str(p) not in known_paths
    ]

    return {
        "models_dir": str(models_dir),
        "llm": llm_models,
        "embeddings": embedding_models,
        "ner": ner_models,
        "other": other_items,
    }


@router.get("/models/status", response_model=ModelLoadResponse)
async def get_model_status():
    """Return current LLM status (active model, device, and fallback state)."""
    llm = get_llm_service()
    return llm.get_status()


@router.post("/models/load", response_model=ModelLoadResponse)
async def load_model(body: ModelLoadRequest):
    """Load a specific GGUF model from the models directory."""
    llm = get_llm_service()
    try:
        await llm.load_model(body.model_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return llm.get_status()


# ============================================================
# PROJECT MANAGEMENT
# ============================================================

@router.post("/projects", response_model=ProjectResponse)
async def create_project(body: ProjectCreate):
    """Create a new research project."""
    from app.core.database import get_session, Project
    import uuid
    from datetime import datetime

    session = get_session()
    try:
        existing = session.query(Project).filter(Project.name == body.name).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Project '{body.name}' already exists")

        project = Project(
            id=str(uuid.uuid4()),
            name=body.name,
            description=body.description,
            created_at=datetime.utcnow(),
        )
        session.add(project)
        session.commit()
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating project: {str(e)}")
    finally:
        session.close()


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects():
    """List all projects."""
    from app.core.database import get_session, Project

    session = get_session()
    try:
        projects = session.query(Project).order_by(Project.created_at.desc()).all()
        return [
            ProjectResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at.isoformat() if p.created_at else "",
            )
            for p in projects
        ]
    finally:
        session.close()


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all its data."""
    from app.core.database import get_session, Project

    session = get_session()
    try:
        project = session.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        session.delete(project)  # Cascade deletes documents, nodes, edges
        session.commit()
        return {"status": "success", "message": f"Deleted project {project_id}"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting project: {str(e)}")
    finally:
        session.close()


# ============================================================
# CHAT (Librarian RAG)
# ============================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Query the knowledge layer using hybrid RAG."""
    ensure_services()
    if chat_service is None:
        raise HTTPException(status_code=503, detail="Chat service unavailable")
    try:
        result = await chat_service.chat(request.query, project_id=request.project_id)
        return ChatResponse(**result)
    except Exception as e:
        logger.exception(f"Query error for request: {request.query[:100]}...")
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


# ============================================================
# DOCUMENT INGESTION
# ============================================================

@router.post("/ingest")
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Query(None),
):
    """Upload and process a PDF through the knowledge layer."""
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_path = Path(settings.UPLOAD_DIR) / file.filename

    ensure_services()
    if ingestion_service is None:
        raise HTTPException(status_code=503, detail="Ingestion service unavailable")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        background_tasks.add_task(
            _process_document_background,
            str(file_path),
            file.filename,
            ingestion_service,
            project_id,
        )

        return {
            "status": "processing",
            "message": f"Document '{file.filename}' uploaded and processing started",
            "filename": file.filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion error for {file.filename}: {str(e)}", exc_info=True)
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


async def _process_document_background(
    file_path: str,
    filename: str,
    ingestion_svc: IngestionService,
    project_id: Optional[str] = None,
):
    """Background task to process document ingestion."""
    try:
        result = await ingestion_svc.ingest_document(file_path, filename, project_id=project_id)
        if result.get("status") == "failed":
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                try:
                    file_path_obj.unlink()
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Background ingestion failed for {filename}: {str(e)}", exc_info=True)
        file_path_obj = Path(file_path)
        if file_path_obj.exists():
            try:
                file_path_obj.unlink()
            except Exception:
                pass


# ============================================================
# FILE MANAGEMENT
# ============================================================

@router.get("/files", response_model=List[Dict[str, Any]])
async def list_files(
    status: Optional[str] = None,
    project_id: Optional[str] = None,
):
    """List all uploaded documents with their status."""
    ensure_services()
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service unavailable")
    try:
        return document_service.list_documents(status=status, project_id=project_id, limit=100)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


@router.get("/files/{doc_id}")
async def get_file(doc_id: str):
    """Stream a PDF file for viewing."""
    ensure_services()
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service unavailable")
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
    """Delete a document from all knowledge layers."""
    ensure_services()
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service unavailable")
    try:
        success = document_service.delete_document(doc_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "success", "message": f"Deleted document {doc_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion error: {str(e)}")


# ============================================================
# KNOWLEDGE GRAPH
# ============================================================

@router.get("/entities", response_model=List[Dict[str, Any]])
async def list_entities(
    entity_type: Optional[str] = None,
    document_id: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """List nodes (entities) in the knowledge graph."""
    ensure_services()
    if graph_service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable")
    try:
        return graph_service.list_nodes(
            label=entity_type, document_id=document_id, project_id=project_id, limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing entities: {str(e)}")


@router.get("/entities/{entity_id}/relationships", response_model=List[Dict[str, Any]])
async def get_entity_relationships(entity_id: str, direction: str = "both"):
    """Get all relationships for a node."""
    ensure_services()
    if graph_service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable")
    try:
        return graph_service.get_node_relationships(entity_id, direction=direction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting relationships: {str(e)}")


@router.get("/graph/types")
async def get_entity_types(project_id: Optional[str] = None):
    """Get all node labels (types) with counts."""
    ensure_services()
    if graph_service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable")
    try:
        return {"entity_types": graph_service.get_node_types(project_id=project_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting types: {str(e)}")


@router.get("/graph/full")
async def get_full_graph(
    document_id: Optional[str] = None,
    project_id: Optional[str] = None,
):
    """Get the complete knowledge graph (nodes + edges)."""
    ensure_services()
    if graph_service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable")
    try:
        return graph_service.get_full_graph(document_id=document_id, project_id=project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting graph: {str(e)}")


# ============================================================
# SWARM (Two-Brain Agentic RAG)
# ============================================================

@router.post("/api/swarm/run", response_model=SwarmResponse)
async def run_swarm(request: SwarmRequest):
    """Run the Two-Brain Swarm on a query within a project.

    The router classifies the query as DEEP_DISCOVERY (Navigator) or
    BROAD_RESEARCH (Cortex) and dispatches accordingly.
    """
    ensure_services()
    try:
        from app.services.swarm import run_swarm_query

        result = await run_swarm_query(
            query=request.query,
            project_id=request.project_id,
            graph_service=graph_service,
            llm_service=chat_service.retrieval_service.llm_service,
            qdrant_client=chat_service.retrieval_service.qdrant_client,
            collection_name=chat_service.retrieval_service.collection_name,
        )
        return SwarmResponse(**result)
    except Exception as e:
        logger.exception("Swarm execution failed")
        raise HTTPException(status_code=500, detail=f"Swarm error: {str(e)}")
