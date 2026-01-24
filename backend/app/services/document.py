"""Document service for file management."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from pathlib import Path
from fastapi.responses import FileResponse

from app.core.database import get_session, Document, DocumentChunk, Node
from app.core.config import settings


class DocumentService:
    """Manages document storage and retrieval."""
    
    def __init__(self):
        self.session: Session = get_session()
    
    def list_documents(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List all documents with optional status filter."""
        query = self.session.query(Document)
        
        if status:
            query = query.filter(Document.status == status)
        
        documents = query.order_by(Document.uploaded_at.desc()).limit(limit).all()
        
        return [self._document_to_dict(d) for d in documents]
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        try:
            from uuid import UUID
            doc_uuid = UUID(doc_id)
        except ValueError:
            return None
        
        document = self.session.query(Document).filter(Document.id == doc_uuid).first()
        
        if not document:
            return None
        
        return self._document_to_dict(document)
    
    def get_document_file(self, doc_id: str) -> Optional[FileResponse]:
        """Get document file for streaming."""
        document = self.get_document(doc_id)
        
        if not document:
            return None
        
        file_path = Path(document["file_path"])
        
        if not file_path.exists():
            return None
        
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=document["filename"]
        )
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document and all its chunks."""
        try:
            from uuid import UUID
            doc_uuid = UUID(doc_id)
        except ValueError:
            return False
        
        document = self.session.query(Document).filter(Document.id == doc_uuid).first()
        
        if not document:
            return False
        
        # Delete file if it exists
        if Path(document.file_path).exists():
            Path(document.file_path).unlink()
        
        # Delete from database (cascades to chunks)
        self.session.delete(document)
        self.session.commit()
        
        return True
    
    def _document_to_dict(self, document: Document) -> Dict[str, Any]:
        """Convert Document ORM object to dictionary."""
        return {
            "filename": document.filename,
            "doc_id": str(document.id),
            "status": document.status,
            "size_bytes": document.file_size,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None
        }
