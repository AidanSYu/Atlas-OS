"""Document service for file management."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from pathlib import Path
from fastapi.responses import FileResponse
import logging

from app.core.database import get_session, Document, DocumentChunk, Node, Edge
from app.core.config import settings

logger = logging.getLogger(__name__)


class DocumentService:
    """Manages document storage and retrieval."""
    
    def __init__(self):
        # Don't create session here - use per-request sessions
        pass
    
    def list_documents(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List all documents with optional status filter. Self-healing: auto-removes orphaned DB records."""
        session = get_session()
        try:
            query = session.query(Document)
            
            if status:
                query = query.filter(Document.status == status)
            
            documents = query.order_by(Document.uploaded_at.desc()).limit(limit).all()
            
            result = []
            orphaned_docs = []
            
            for doc in documents:
                # Self-healing: check if file exists (quick check)
                try:
                    file_path = Path(doc.file_path)
                    if not file_path.exists():
                        # File missing from disk - mark as orphaned for deletion
                        orphaned_docs.append(doc)
                        continue
                except Exception:
                    # If file_path is invalid, skip it
                    orphaned_docs.append(doc)
                    continue
                
                result.append(self._document_to_dict(doc))
            
            # Auto-delete orphaned database records to keep sidebar clean
            # Do this in a separate transaction to avoid blocking
            if orphaned_docs:
                logger.info(f"Auto-deleting {len(orphaned_docs)} orphaned document records (files missing from disk)")
                for orphaned_doc in orphaned_docs:
                    try:
                        session.delete(orphaned_doc)
                    except Exception as e:
                        logger.error(f"Error deleting orphaned document {orphaned_doc.id}: {e}")
                try:
                    session.commit()
                except Exception as e:
                    logger.error(f"Error committing orphaned document deletions: {e}")
                    session.rollback()
            
            return result
        finally:
            session.close()
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        session = get_session()
        try:
            try:
                from uuid import UUID
                doc_uuid = UUID(doc_id)
            except ValueError:
                return None
            
            document = session.query(Document).filter(Document.id == doc_uuid).first()
            
            if not document:
                return None
            
            return self._document_to_dict(document)
        finally:
            session.close()
    
    def get_document_file(self, doc_id: str) -> Optional[FileResponse]:
        """Get document file for streaming."""
        session = get_session()
        try:
            try:
                from uuid import UUID
                doc_uuid = UUID(doc_id)
            except ValueError:
                return None
            
            document = session.query(Document).filter(Document.id == doc_uuid).first()
            
            if not document:
                return None
            
            # Get file_path directly from the document object
            file_path = Path(document.file_path)
            
            if not file_path.exists():
                logger.warning(f"File not found for document {doc_id}: {file_path}")
                return None
            
            return FileResponse(
                path=file_path,
                media_type="application/pdf",
                filename=document.filename
            )
        finally:
            session.close()
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document from all knowledge layers: filesystem, Qdrant, and PostgreSQL."""
        session = get_session()
        try:
            try:
                from uuid import UUID
                doc_uuid = UUID(doc_id)
            except ValueError:
                return False
            
            document = session.query(Document).filter(Document.id == doc_uuid).first()
            
            if not document:
                return False
            
            doc_id_str = str(doc_id)
            
            # 1. Delete from Qdrant vector store
            try:
                from qdrant_client import QdrantClient
                from app.core.config import settings
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                
                qdrant_client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT
                )
                
                # Delete all chunks for this document from Qdrant
                # Chunk IDs are generated as: uuid.uuid5(doc_id, f"chunk-{chunk_index}")
                # We need to find all points with doc_id in payload
                filter_condition = Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id_str)
                        )
                    ]
                )
                
                # Scroll to get all point IDs matching this document
                point_ids = []
                offset = None
                while True:
                    scroll_result = qdrant_client.scroll(
                        collection_name=settings.QDRANT_COLLECTION,
                        scroll_filter=filter_condition,
                        limit=100,
                        offset=offset
                    )
                    
                    points, next_offset = scroll_result
                    if not points:
                        break
                    
                    point_ids.extend([point.id for point in points])
                    
                    if next_offset is None:
                        break
                    offset = next_offset
                
                # Delete all found points
                if point_ids:
                    qdrant_client.delete(
                        collection_name=settings.QDRANT_COLLECTION,
                        points_selector=point_ids
                    )
                    logger.info(f"Deleted {len(point_ids)} vectors from Qdrant for document {doc_id_str}")
                else:
                    logger.info(f"No vectors found in Qdrant for document {doc_id_str}")
            except Exception as e:
                logger.warning(f"Error deleting from Qdrant for document {doc_id_str}: {e}")
                # Continue with deletion even if Qdrant deletion fails
            
            # 2. Delete related nodes and edges from knowledge graph
            try:
                # Find all nodes associated with this document
                nodes = session.query(Node).filter(
                    Node.properties['document_id'].astext == doc_id_str
                ).all()
                
                node_ids = [node.id for node in nodes]
                
                if node_ids:
                    # Delete all edges connected to these nodes
                    edges_deleted = session.query(Edge).filter(
                        (Edge.source_id.in_(node_ids)) | (Edge.target_id.in_(node_ids))
                    ).delete(synchronize_session=False)
                    
                    # Delete the nodes themselves
                    nodes_deleted = session.query(Node).filter(
                        Node.id.in_(node_ids)
                    ).delete(synchronize_session=False)
                    
                    logger.info(f"Deleted {nodes_deleted} nodes and {edges_deleted} edges from knowledge graph for document {doc_id_str}")
            except Exception as e:
                logger.warning(f"Error deleting nodes/edges from knowledge graph for document {doc_id_str}: {e}")
                # Continue with deletion even if graph cleanup fails
            
            # 3. Delete file if it exists - graceful deletion: proceed even if file is missing
            try:
                file_path = Path(document.file_path)
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted file: {document.file_path}")
            except FileNotFoundError:
                # File already missing - that's okay, proceed with DB cleanup
                pass
            except Exception as e:
                # Log other file deletion errors but don't fail the operation
                logger.warning(f"Error deleting file {document.file_path}: {e}")
            
            # 4. Delete from database (cascades to chunks) - always proceed even if file was missing
            session.delete(document)
            session.commit()
            
            logger.info(f"Successfully deleted document {doc_id_str}")
            return True
        except Exception as e:
            logger.error(f"Error during document deletion: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def _document_to_dict(self, document: Document) -> Dict[str, Any]:
        """Convert Document ORM object to dictionary."""
        # Map backend status to frontend expected status
        status = document.status
        if status == "completed":
            status = "indexed"  # Frontend expects "indexed" for completed documents
        
        return {
            "filename": document.filename,
            "doc_id": str(document.id),
            "status": status,
            "size_bytes": document.file_size,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None
        }
