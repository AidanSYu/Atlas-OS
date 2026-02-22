"""FastAPI route handlers for Atlas Sidecar API."""
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import json
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
context_engine_service = None
workspace_service = None

logger = logging.getLogger(__name__)


async def monitor_disconnect(request: Request, cancel_event: asyncio.Event, poll_interval: float = 0.5):
    """Poll for client disconnect and set the cancel event when detected."""
    while not cancel_event.is_set():
        if await request.is_disconnected():
            cancel_event.set()
            logger.info("Client disconnected - cancellation signal sent")
            return
        await asyncio.sleep(poll_interval)



def ensure_services():
    """Initialize services - FATAL on failure."""
    global chat_service, ingestion_service, document_service, graph_service, context_engine_service, workspace_service

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
    if context_engine_service is None:
        from app.services.context_engine import ContextEngineService
        context_engine_service = ContextEngineService()
        logger.info("ContextEngineService initialized")
    if workspace_service is None:
        from app.services.workspace import WorkspaceService
        workspace_service = WorkspaceService()
        logger.info("WorkspaceService initialized")


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
    

class SwarmStreamRequest(BaseModel):
    project_id: str
    query: str
    session_id: Optional[str] = None


class SwarmResponse(BaseModel):
    brain_used: str  # "librarian", "navigator", or "cortex"
    hypothesis: str
    evidence: List[Dict[str, Any]]
    reasoning_trace: List[str]
    status: str
    # Task 0.3: New fields for Navigator 2.0 / Cortex 2.0
    confidence_score: Optional[float] = None
    iterations: Optional[int] = None
    contradictions: List[Dict[str, Any]] = []


class ModelLoadRequest(BaseModel):
    model_name: str


class ModelLoadResponse(BaseModel):
    active_model: Optional[str]
    model_type: str
    device: str
    gpu_layers: int
    fallback: bool
    model_source: str = "local"           # Atlas 3.0: "local" or "api"
    api_models_available: bool = False     # Atlas 3.0: Whether API models are configured


class ContextRequest(BaseModel):
    project_id: str
    selected_text: Optional[str] = None
    current_doc_id: Optional[str] = None
    current_page: Optional[int] = None


class ConfigKeys(BaseModel):
    has_openai: bool
    has_anthropic: bool
    has_deepseek: bool
    has_minimax: bool

class ConfigKeysUpdate(BaseModel):
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    MINIMAX_API_KEY: Optional[str] = None

# ============================================================
# HEALTH / INFO
# ============================================================

@router.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Atlas API - Agentic MoE Knowledge Engine",
        "version": "3.0.0-sidecar",
        "architecture": {
            "database": "SQLite (embedded)",
            "vector_store": "Qdrant (embedded, in-process)",
            "knowledge_graph": "Evidence-Bound GraphRAG",
            "llm": "Hybrid (local GGUF + LiteLLM API)",
            "workspace": "Persistent Markdown/JSON Drafts",
            "swarm": "LangGraph MoE (Supervisor + Expert Agents)",
            "retrieval": "BM25 + Vector + RRF + FlashRank",
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


@router.get("/config/keys", response_model=ConfigKeys)
async def get_config_keys():
    """Return flags indicating which API keys are stored."""
    return {
        "has_openai": bool(settings.OPENAI_API_KEY),
        "has_anthropic": bool(settings.ANTHROPIC_API_KEY),
        "has_deepseek": bool(settings.DEEPSEEK_API_KEY),
        "has_minimax": bool(settings.MINIMAX_API_KEY),
    }


class ConfigKeysVerifyResponse(BaseModel):
    """Result of verifying each provider's API key with a minimal API call."""
    openai: bool
    anthropic: bool
    deepseek: bool
    minimax: bool


@router.post("/config/keys/verify", response_model=ConfigKeysVerifyResponse)
async def verify_config_keys():
    """Verify each configured API key with a minimal API call. Does not persist state."""
    import os
    result = {"openai": False, "anthropic": False, "deepseek": False, "minimax": False}
    try:
        import litellm
    except ImportError:
        return ConfigKeysVerifyResponse(**result)

    async def _verify(model: str, env_key: str) -> bool:
        key = getattr(settings, env_key, None) or ""
        if not key or not key.strip():
            return False
        # Ensure the env var is set for LiteLLM (and leave it set if valid)
        os.environ[env_key] = key
        try:
            resp = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1,
            )
            verified = bool(resp and resp.choices and resp.choices[0].message)
            logger.info(f"API key verify {env_key} ({model}): {'OK' if verified else 'empty response'}")
            return verified
        except Exception as e:
            logger.warning(f"API key verify {env_key} ({model}) failed: {e}")
            return False

    if settings.OPENAI_API_KEY:
        result["openai"] = await _verify("gpt-4o-mini", "OPENAI_API_KEY")
    if settings.ANTHROPIC_API_KEY:
        result["anthropic"] = await _verify("claude-3-haiku-20240307", "ANTHROPIC_API_KEY")
    if settings.DEEPSEEK_API_KEY:
        result["deepseek"] = await _verify("deepseek/deepseek-chat", "DEEPSEEK_API_KEY")
    if settings.MINIMAX_API_KEY:
        result["minimax"] = await _verify("minimax/MiniMax-M2.5", "MINIMAX_API_KEY")

    return ConfigKeysVerifyResponse(**result)


@router.post("/config/keys")
async def update_config_keys(keys: ConfigKeysUpdate):
    """Update API keys in the .env file and application memory."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    
    # Read existing env
    env_lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            env_lines = f.readlines()
            
    import os as _os
    updates = {}
    if keys.OPENAI_API_KEY is not None:
        updates["OPENAI_API_KEY"] = keys.OPENAI_API_KEY
        settings.OPENAI_API_KEY = keys.OPENAI_API_KEY
    if keys.ANTHROPIC_API_KEY is not None:
        updates["ANTHROPIC_API_KEY"] = keys.ANTHROPIC_API_KEY
        settings.ANTHROPIC_API_KEY = keys.ANTHROPIC_API_KEY
    if keys.DEEPSEEK_API_KEY is not None:
        updates["DEEPSEEK_API_KEY"] = keys.DEEPSEEK_API_KEY
        settings.DEEPSEEK_API_KEY = keys.DEEPSEEK_API_KEY
    if keys.MINIMAX_API_KEY is not None:
        updates["MINIMAX_API_KEY"] = keys.MINIMAX_API_KEY
        settings.MINIMAX_API_KEY = keys.MINIMAX_API_KEY

    # Sync to os.environ so LiteLLM can find the keys at runtime
    # (LiteLLM reads env vars, not the settings object)
    for env_key, env_val in updates.items():
        if env_val:
            _os.environ[env_key] = env_val
        elif env_key in _os.environ:
            del _os.environ[env_key]
        
    if not updates:
        return {"status": "success", "message": "No keys provided to update"}
        
    # Write updated env
    try:
        new_lines = []
        updated_keys = set()
        for line in env_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue
                
            parts = stripped.split("=", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                if key in updates:
                    new_lines.append(f'{key}="{updates[key]}"\n')
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
                
        # Append keys that weren't already in the file
        for key, value in updates.items():
            if key not in updated_keys:
                new_lines.append(f'{key}="{value}"\n')
                
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to update API keys: {e}")
        raise HTTPException(status_code=500, detail="Failed to save API keys configuration")


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
    """Load a model - either a local GGUF or an API model.

    Atlas 3.0: Accepts both local model filenames (e.g., "Phi-3.5-mini-instruct.Q4_K_M.gguf")
    and API model identifiers (e.g., "deepseek/deepseek-chat").
    Models with "/" are treated as API models and routed through LiteLLM.
    """
    llm = get_llm_service()
    try:
        await llm.load_model(body.model_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return llm.get_status()


@router.get("/models/registry")
async def get_model_registry():
    """Atlas 3.0: Get the full model registry (local + cloud API models).

    Returns grouped lists for the frontend model selector:
    - local: GGUF models in the models directory
    - api: Cloud API models available via LiteLLM (with key status)
    - active: Currently loaded model info
    """
    llm = get_llm_service()

    # Local models
    local_models = [
        {"name": name, "source": "local", "provider": "local"}
        for name in llm.list_available_models()
    ]

    # API models
    api_models = llm.list_available_api_models()

    # Current status
    status = llm.get_status()

    return {
        "local": local_models,
        "api": api_models,
        "active": status,
    }


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

# Supported file extensions for document ingestion
SUPPORTED_FILE_EXTENSIONS = ('.pdf', '.txt', '.docx', '.doc')

@router.post("/ingest")
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Query(None),
):
    """Upload and process a document (PDF, DOCX, DOC, TXT) through the knowledge layer."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Check if file extension is supported
    file_lower = file.filename.lower()
    if not any(file_lower.endswith(ext) for ext in SUPPORTED_FILE_EXTENSIONS):
        supported = ', '.join(SUPPORTED_FILE_EXTENSIONS)
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Supported formats: {supported}"
        )

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
        else:
            # Invalidate graph cache so new entities appear immediately
            if graph_service is not None:
                graph_service.invalidate_cache()
                logger.info(f"Graph cache invalidated after ingesting {filename}")
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
        return await graph_service.get_full_graph_cached(document_id=document_id, project_id=project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting graph: {str(e)}")


# ============================================================
# SWARM (Two-Brain Agentic RAG)
# ============================================================

@router.post("/api/swarm/stream")
async def stream_swarm(body: SwarmStreamRequest, request: Request):
    """Stream swarm execution via Server-Sent Events.

    Event types:
      - routing:  {"brain": "navigator", "intent": "DEEP_DISCOVERY"}
      - progress: {"node": "planner", "message": "Planning research strategy..."}
      - thinking: {"content": "Step 1: Analyzing the query..."}
      - chunk:    {"content": "partial answer text"}  (token streaming)
      - evidence: {"source": "file.pdf", "page": 5, "excerpt": "..."}
      - grounding: {"claim": "...", "status": "GROUNDED", "confidence": 0.9}
      - complete: {"hypothesis": "full answer", "confidence": 0.85, ...}
      - cancelled: {"message": "Generation stopped by user"}
      - error:    {"message": "..."}
    """
    ensure_services()
    if chat_service is None or graph_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized. Check backend logs.")

    async def event_generator():
        cancel_event = asyncio.Event()
        monitor_task = asyncio.create_task(monitor_disconnect(request, cancel_event))
        try:
            from app.services.swarm import run_swarm_query_streaming

            async for event_type, event_data in run_swarm_query_streaming(
                query=body.query,
                project_id=body.project_id,
                session_id=body.session_id,
                graph_service=graph_service,
                llm_service=chat_service.retrieval_service.llm_service,
                qdrant_client=chat_service.retrieval_service.qdrant_client,
                collection_name=chat_service.retrieval_service.collection_name,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    yield f"event: cancelled\ndata: {json.dumps({'message': 'Generation stopped by user'})}\n\n"
                    break
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        finally:
            cancel_event.set()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/swarm/run", response_model=SwarmResponse)
async def run_swarm(request: SwarmRequest):
    """Run the Two-Brain Swarm on a query within a project.

    The router classifies the query as DEEP_DISCOVERY (Navigator) or
    BROAD_RESEARCH (Cortex) and dispatches accordingly.
    """
    ensure_services()
    if chat_service is None or graph_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized. Check backend logs.")
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
        err_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
        raise HTTPException(status_code=500, detail=f"Swarm error: {err_msg}")


# ============================================================
# ATLAS 3.0: MoE (Mixture of Experts) Agentic RAG
# ============================================================

class MoERequest(BaseModel):
    project_id: str
    query: str
    session_id: Optional[str] = None


@router.post("/api/moe/run")
async def run_moe(request: MoERequest):
    """Atlas 3.0: Run the Mixture of Experts pipeline on a query.

    The MoE pipeline uses a Supervisor agent to orchestrate specialized
    Expert agents (Hypothesis, Retrieval, Writer, Critic) for multi-turn
    research with grounding verification.
    """
    ensure_services()
    if chat_service is None or graph_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized. Check backend logs.")
    try:
        from app.services.swarm import run_moe_query

        result = await run_moe_query(
            query=request.query,
            project_id=request.project_id,
            graph_service=graph_service,
            llm_service=chat_service.retrieval_service.llm_service,
            qdrant_client=chat_service.retrieval_service.qdrant_client,
            collection_name=chat_service.retrieval_service.collection_name,
        )
        return result
    except Exception as e:
        logger.exception("MoE execution failed")
        raise HTTPException(status_code=500, detail=f"MoE error: {str(e)}")


@router.post("/api/moe/stream")
async def stream_moe(body: MoERequest, request: Request):
    """Atlas 3.0: Stream MoE execution via Server-Sent Events.

    Event types:
      - routing:    {"brain": "moe_supervisor", "intent": "MoE"}
      - progress:   {"node": "hypothesis", "message": "Generating hypotheses..."}
      - thinking:   {"content": "[Supervisor] Planning..."}
      - hypotheses: {"items": [...], "selected": "..."}
      - evidence:   {"items": [...], "count": N}
      - grounding:  {"results": [...], "verdict": "PASS|REVISE"}
      - complete:   {"hypothesis": "final answer", "confidence": 0.85, ...}
      - cancelled:  {"message": "Generation stopped by user"}
      - error:      {"message": "..."}
    """
    ensure_services()
    if chat_service is None or graph_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized. Check backend logs.")

    async def event_generator():
        cancel_event = asyncio.Event()
        monitor_task = asyncio.create_task(monitor_disconnect(request, cancel_event))
        try:
            from app.services.swarm import run_moe_query_streaming

            async for event_type, event_data in run_moe_query_streaming(
                query=body.query,
                project_id=body.project_id,
                session_id=body.session_id,
                graph_service=graph_service,
                llm_service=chat_service.retrieval_service.llm_service,
                qdrant_client=chat_service.retrieval_service.qdrant_client,
                collection_name=chat_service.retrieval_service.collection_name,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    yield f"event: cancelled\ndata: {json.dumps({'message': 'Generation stopped by user'})}\n\n"
                    break
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
        except Exception as e:
            logger.error(f"MoE streaming error: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        finally:
            cancel_event.set()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.post("/api/moe/hypotheses")
async def stream_moe_hypotheses(body: MoERequest, request: Request):
    """Atlas 3.0: Stream MoE interactive hypotheses generation via SSE.
    """
    ensure_services()
    if chat_service is None or graph_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized. Check backend logs.")

    async def event_generator():
        cancel_event = asyncio.Event()
        monitor_task = asyncio.create_task(monitor_disconnect(request, cancel_event))
        try:
            from app.services.swarm import generate_moe_hypotheses

            async for event_type, event_data in generate_moe_hypotheses(
                query=body.query,
                project_id=body.project_id,
                session_id=body.session_id,
                graph_service=graph_service,
                llm_service=chat_service.retrieval_service.llm_service,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    yield f"event: cancelled\ndata: {json.dumps({'message': 'Generation stopped by user'})}\n\n"
                    break
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
        except Exception as e:
            logger.error(f"MoE hypotheses streaming error: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        finally:
            cancel_event.set()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# ============================================================
# CONTEXT ENGINE (Phase 4: Smart Reading & Context)
# ============================================================

@router.get("/files/{doc_id}/structure")
async def get_document_structure(doc_id: str):
    """Get extracted paper structure (title, authors, methods, findings)."""
    ensure_services()
    if context_engine_service is None:
        raise HTTPException(status_code=503, detail="Context engine unavailable")
    try:
        result = await context_engine_service.get_document_structure(doc_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting document structure: {str(e)}")


@router.get("/files/{doc_id}/related")
async def get_related_passages(
    doc_id: str,
    text: str = Query(..., min_length=3),
    project_id: Optional[str] = Query(None),
    limit: int = Query(8, ge=1, le=20),
):
    """Find passages in other documents related to selected text."""
    ensure_services()
    if context_engine_service is None:
        raise HTTPException(status_code=503, detail="Context engine unavailable")
    try:
        return await context_engine_service.get_related_passages(
            doc_id=doc_id, text=text, project_id=project_id, limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding related passages: {str(e)}")


@router.get("/files/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    page: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Get chunks for a document, optionally filtered by page number."""
    ensure_services()
    if context_engine_service is None:
        raise HTTPException(status_code=503, detail="Context engine unavailable")
    try:
        return await context_engine_service.get_document_chunks(
            doc_id=doc_id, page_number=page, limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting document chunks: {str(e)}")


@router.post("/api/context")
async def get_context_suggestions(request: ContextRequest):
    """Get context-aware suggestions based on user's current focus.

    Accepts a context snapshot (selected text, current document/page)
    and returns related passages, connected entities, and suggestions.
    """
    ensure_services()
    if context_engine_service is None:
        raise HTTPException(status_code=503, detail="Context engine unavailable")
    try:
        return await context_engine_service.get_context_suggestions(
            project_id=request.project_id,
            selected_text=request.selected_text,
            current_doc_id=request.current_doc_id,
            current_page=request.current_page,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting context suggestions: {str(e)}")


# ============================================================
# IMPORT / EXPORT (Phase 5)
# ============================================================

class ExportMarkdownRequest(BaseModel):
    content: str
    citations: List[Dict[str, Any]] = []
    project_id: str
    title: str = "Research Synthesis"
    author: str = ""
    style: str = "apa"  # apa, mla, chicago


class ExportChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    project_name: str = "Atlas Research"


class FormatCitationRequest(BaseModel):
    doc_ids: List[str]
    style: str = "apa"


@router.post("/import/bibtex")
async def import_bibtex(
    file: UploadFile = File(...),
    project_id: str = Query(...),
):
    """Import papers from a BibTeX (.bib) or RIS (.ris) file.

    Creates Document records with status='metadata_only' for each entry.
    PDFs can be attached to these records later via the ingest endpoint.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    filename_lower = file.filename.lower()
    content = (await file.read()).decode("utf-8", errors="replace")

    try:
        if filename_lower.endswith(".bib"):
            from app.services.importers.bibtex import BibTeXImporter
            importer = BibTeXImporter()
            result = importer.import_from_string(content, project_id)
        elif filename_lower.endswith(".ris"):
            from app.services.importers.bibtex import RISImporter
            importer = RISImporter()
            result = importer.import_from_string(content, project_id)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported format. Use .bib (BibTeX) or .ris (RIS).",
            )

        if result.get("status") == "failed":
            raise HTTPException(status_code=500, detail=result.get("error", "Import failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Import error: {str(e)}")


@router.get("/export/bibtex/{project_id}")
async def export_bibtex(project_id: str):
    """Export all project citations as a BibTeX (.bib) file."""
    try:
        from app.services.exporters.bibtex import BibTeXExporter
        exporter = BibTeXExporter()
        bib_content = exporter.export_project(project_id)

        if not bib_content:
            return {"status": "empty", "message": "No documents with metadata found in this project"}

        return StreamingResponse(
            iter([bib_content]),
            media_type="application/x-bibtex",
            headers={
                "Content-Disposition": f'attachment; filename="atlas-{project_id[:8]}.bib"',
            },
        )
    except Exception as e:
        logger.error(f"BibTeX export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")


@router.post("/export/bibtex")
async def export_bibtex_selection(body: FormatCitationRequest):
    """Export specific documents as BibTeX entries."""
    try:
        from app.services.exporters.bibtex import BibTeXExporter
        exporter = BibTeXExporter()
        bib_content = exporter.export_documents(body.doc_ids)

        if not bib_content:
            return {"status": "empty", "message": "No documents found for the given IDs"}

        return StreamingResponse(
            iter([bib_content]),
            media_type="application/x-bibtex",
            headers={
                "Content-Disposition": 'attachment; filename="atlas-selection.bib"',
            },
        )
    except Exception as e:
        logger.error(f"BibTeX export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")


@router.post("/export/markdown")
async def export_markdown(body: ExportMarkdownRequest):
    """Export synthesis as Pandoc-compatible Markdown.

    Returns a JSON object with:
    - markdown: The full Markdown document with YAML front matter
    - bibtex: Companion .bib file content for Pandoc
    - filename: Suggested filename (without extension)
    """
    try:
        from app.services.exporters.markdown import MarkdownExporter
        exporter = MarkdownExporter()
        result = exporter.export_synthesis(
            content=body.content,
            citations=body.citations,
            project_id=body.project_id,
            title=body.title,
            author=body.author,
            style=body.style,
        )
        return result
    except Exception as e:
        logger.error(f"Markdown export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")


@router.post("/export/chat")
async def export_chat_history(body: ExportChatRequest):
    """Export a chat conversation as Markdown."""
    try:
        from app.services.exporters.markdown import MarkdownExporter
        exporter = MarkdownExporter()
        md_content = exporter.export_chat_history(
            messages=body.messages,
            project_name=body.project_name,
        )
        return {"markdown": md_content}
    except Exception as e:
        logger.error(f"Chat export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")


@router.post("/export/citations/format")
async def format_citations(body: FormatCitationRequest):
    """Format citations for specific documents in a given style (APA/MLA/Chicago)."""
    try:
        from app.core.database import get_session, Document as DocModel
        from app.services.exporters.bibtex import BibTeXExporter

        exporter = BibTeXExporter()
        session = get_session()
        try:
            documents = (
                session.query(DocModel)
                .filter(DocModel.id.in_(body.doc_ids))
                .all()
            )
            formatted = []
            for doc in documents:
                meta = doc.doc_metadata or {}
                citation = exporter.format_citation(meta, body.style)
                formatted.append({
                    "doc_id": doc.id,
                    "filename": doc.filename,
                    "citation": citation,
                    "bibtex_key": meta.get("bibtex_key", ""),
                })
            return {"citations": formatted, "style": body.style}
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Citation format error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Format error: {str(e)}")
