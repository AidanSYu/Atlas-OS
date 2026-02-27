"""Document service for file management (SQLite + embedded Qdrant)."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from pathlib import Path
from fastapi.responses import FileResponse
import logging

from app.core.database import get_session, Document, DocumentChunk, Node, Edge
from app.core.config import settings
from app.core.qdrant_store import get_qdrant_client
from app.services.bm25_index import get_bm25_service

logger = logging.getLogger(__name__)


class DocumentService:
    """Manages document storage and retrieval."""

    def __init__(self):
        pass

    def list_documents(
        self,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List all documents with optional status/project filter. Self-healing for orphaned records."""
        session = get_session()
        try:
            query = session.query(Document)

            if status:
                query = query.filter(Document.status == status)
            if project_id:
                query = query.filter(Document.project_id == project_id)

            documents = query.order_by(Document.uploaded_at.desc()).limit(limit).all()

            result = []
            orphaned_docs = []

            for doc in documents:
                try:
                    file_path = Path(doc.file_path)
                    if not file_path.exists():
                        orphaned_docs.append(doc)
                        continue
                except Exception:
                    orphaned_docs.append(doc)
                    continue

                result.append(self._document_to_dict(doc))

            # Auto-delete orphaned database records
            if orphaned_docs:
                logger.info(f"Auto-deleting {len(orphaned_docs)} orphaned document records")
                for orphaned_doc in orphaned_docs:
                    try:
                        session.query(DocumentChunk).filter(
                            DocumentChunk.document_id == orphaned_doc.id
                        ).delete(synchronize_session=False)
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
            document = session.query(Document).filter(Document.id == doc_id).first()
            if not document:
                return None
            return self._document_to_dict(document)
        finally:
            session.close()

    def get_document_file(self, doc_id: str) -> Optional[FileResponse]:
        """Get document file for streaming."""
        session = get_session()
        try:
            document = session.query(Document).filter(Document.id == doc_id).first()
            if not document:
                return None

            file_path = Path(document.file_path)
            if not file_path.exists():
                logger.warning(f"File not found for document {doc_id}: {file_path}")
                return None

            mime_map = {
                ".pdf": "application/pdf",
                ".txt": "text/plain",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".doc": "application/msword",
            }
            ext = file_path.suffix.lower()
            media_type = mime_map.get(ext, "application/octet-stream")

            return FileResponse(
                path=file_path, media_type=media_type, filename=document.filename
            )
        finally:
            session.close()

    def delete_document(self, doc_id: str) -> bool:
        """Delete document from all knowledge layers."""
        session = get_session()
        try:
            document = session.query(Document).filter(Document.id == doc_id).first()
            if not document:
                return False

            doc_id_str = str(doc_id)

            # 1. Delete from Qdrant vector store (use shared singleton client)
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                qdrant_client = get_qdrant_client()

                filter_condition = Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id_str))]
                )

                point_ids = []
                offset = None
                while True:
                    scroll_result = qdrant_client.scroll(
                        collection_name=settings.QDRANT_COLLECTION,
                        scroll_filter=filter_condition,
                        limit=100,
                        offset=offset,
                    )
                    points, next_offset = scroll_result
                    if not points:
                        break
                    point_ids.extend([point.id for point in points])
                    if next_offset is None:
                        break
                    offset = next_offset

                if point_ids:
                    qdrant_client.delete(
                        collection_name=settings.QDRANT_COLLECTION, points_selector=point_ids
                    )
                    logger.info(f"Deleted {len(point_ids)} vectors from Qdrant for doc {doc_id_str}")
            except Exception as e:
                logger.warning(f"Error deleting from Qdrant for doc {doc_id_str}: {e}")

            # 1.5. Remove from BM25 sparse index
            try:
                get_bm25_service().remove_document(doc_id_str)
                logger.info(f"Removed doc {doc_id_str} from BM25 index")
            except Exception as e:
                logger.warning(f"Error removing from BM25 index for doc {doc_id_str}: {e}")

            # 2. Delete document chunks
            try:
                session.query(DocumentChunk).filter(
                    DocumentChunk.document_id == doc_id
                ).delete(synchronize_session=False)
            except Exception as e:
                logger.warning(f"Error deleting chunks for doc {doc_id_str}: {e}")

            # 3. Delete related nodes and edges
            try:
                nodes = session.query(Node).filter(Node.document_id == doc_id).all()
                node_ids = [node.id for node in nodes]

                if node_ids:
                    session.query(Edge).filter(
                        (Edge.source_id.in_(node_ids)) | (Edge.target_id.in_(node_ids))
                    ).delete(synchronize_session=False)

                    session.query(Node).filter(
                        Node.document_id == doc_id
                    ).delete(synchronize_session=False)
            except Exception as e:
                logger.warning(f"Error deleting nodes/edges for doc {doc_id_str}: {e}")

            # 4. Delete file
            try:
                file_path = Path(document.file_path)
                if file_path.exists():
                    file_path.unlink()
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Error deleting file {document.file_path}: {e}")

            # 5. Delete from database
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
        status = document.status
        if status == "completed":
            status = "indexed"

        progress = 0.0
        if document.total_chunks and document.total_chunks > 0:
            progress = min(100.0, (document.processed_chunks / document.total_chunks) * 100.0)

        return {
            "filename": document.filename,
            "doc_id": str(document.id),
            "status": status,
            "size_bytes": document.file_size,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None,
            "total_chunks": document.total_chunks,
            "processed_chunks": document.processed_chunks,
            "progress": round(progress, 1),
            "project_id": document.project_id,
        }
