"""
Document Store Module - PostgreSQL-backed document management.

This module handles:
1. Document upload and storage
2. Chunk management
3. Document metadata and provenance
4. Deduplication via hashing
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database import Document, DocumentChunk, get_session
import uuid
import hashlib
from datetime import datetime
from pathlib import Path

class DocumentStore:
    """Manages document storage and retrieval."""
    
    def __init__(self):
        self.session: Session = get_session()
    
    def add_document(
        self,
        filename: str,
        file_path: str,
        file_size: int,
        mime_type: str = "application/pdf",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a new document to the store.
        
        Returns:
            Document info including ID and hash check
        """
        # Calculate file hash for deduplication
        file_hash = self._calculate_hash(file_path)
        
        # Check if document already exists
        existing = self.session.query(Document).filter(
            Document.file_hash == file_hash
        ).first()
        
        if existing:
            return {
                "doc_id": existing.id,
                "status": "duplicate",
                "message": f"Document already exists as {existing.filename}",
                "existing_doc": self._document_to_dict(existing)
            }
        
        # Create new document
        doc_id = str(uuid.uuid4())
        document = Document(
            id=doc_id,
            filename=filename,
            file_hash=file_hash,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            uploaded_at=datetime.utcnow(),
            status="pending",
            metadata=metadata or {}
        )
        
        self.session.add(document)
        self.session.commit()
        
        return {
            "doc_id": doc_id,
            "status": "new",
            "message": "Document added successfully"
        }
    
    def add_chunks(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Add chunks for a document.
        
        Args:
            chunks: List with structure:
                {
                    "text": str,
                    "chunk_index": int,
                    "page_number": int,
                    "metadata": dict
                }
        
        Returns:
            List of chunk IDs
        """
        chunk_ids = []
        
        for chunk_data in chunks:
            chunk_id = f"{document_id}_chunk_{chunk_data['chunk_index']}"
            
            chunk = DocumentChunk(
                id=chunk_id,
                document_id=document_id,
                text=chunk_data["text"],
                chunk_index=chunk_data["chunk_index"],
                page_number=chunk_data.get("page_number"),
                start_char=chunk_data.get("start_char"),
                end_char=chunk_data.get("end_char"),
                metadata=chunk_data.get("metadata", {})
            )
            
            self.session.add(chunk)
            chunk_ids.append(chunk_id)
        
        self.session.commit()
        return chunk_ids
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        document = self.session.query(Document).filter(Document.id == doc_id).first()
        
        if not document:
            return None
        
        return self._document_to_dict(document)
    
    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get chunk by ID."""
        chunk = self.session.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
        
        if not chunk:
            return None
        
        return self._chunk_to_dict(chunk)
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        chunks = self.session.query(DocumentChunk).filter(
            DocumentChunk.document_id == doc_id
        ).order_by(DocumentChunk.chunk_index).all()
        
        return [self._chunk_to_dict(c) for c in chunks]
    
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
    
    def update_document_status(
        self,
        doc_id: str,
        status: str,
        processed_at: Optional[datetime] = None
    ):
        """Update document processing status."""
        document = self.session.query(Document).filter(Document.id == doc_id).first()
        
        if document:
            document.status = status
            if processed_at:
                document.processed_at = processed_at
            elif status == "completed":
                document.processed_at = datetime.utcnow()
            
            self.session.commit()
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document and all its chunks."""
        document = self.session.query(Document).filter(Document.id == doc_id).first()
        
        if not document:
            return False
        
        # Delete file if it exists
        if Path(document.file_path).exists():
            Path(document.file_path).unlink()
        
        # Delete from database (cascades to chunks)
        self.session.delete(document)
        self.session.commit()
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get document store statistics."""
        total_docs = self.session.query(Document).count()
        total_chunks = self.session.query(DocumentChunk).count()
        
        status_counts = {}
        for status in ["pending", "processing", "completed", "failed"]:
            count = self.session.query(Document).filter(Document.status == status).count()
            status_counts[status] = count
        
        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "status_breakdown": status_counts
        }
    
    def _calculate_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def _document_to_dict(self, document: Document) -> Dict[str, Any]:
        """Convert Document ORM object to dictionary."""
        return {
            "id": document.id,
            "filename": document.filename,
            "file_hash": document.file_hash,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "mime_type": document.mime_type,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None,
            "status": document.status,
            "metadata": document.metadata
        }
    
    def _chunk_to_dict(self, chunk: DocumentChunk) -> Dict[str, Any]:
        """Convert DocumentChunk ORM object to dictionary."""
        return {
            "id": chunk.id,
            "document_id": chunk.document_id,
            "text": chunk.text,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "metadata": chunk.metadata
        }
