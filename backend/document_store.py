"""Document store management."""
from typing import List, Dict, Any, Optional
from database import get_session, Document

class DocumentStore:
    def __init__(self):
        pass
    
    def list_documents(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        session = get_session()
        try:
            query = session.query(Document)
            if status:
                query = query.filter(Document.status == status)
            
            documents = query.limit(limit).all()
            
            return [
                {
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "status": doc.status,
                    "file_size": doc.file_size,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "processed_at": doc.processed_at.isoformat() if doc.processed_at else None
                }
                for doc in documents
            ]
        finally:
            session.close()
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        session = get_session()
        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if doc:
                return {
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "file_path": doc.file_path,
                    "status": doc.status
                }
            return None
        finally:
            session.close()
    
    def delete_document(self, doc_id: str) -> bool:
        session = get_session()
        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if doc:
                session.delete(doc)
                session.commit()
                return True
            return False
        finally:
            session.close()