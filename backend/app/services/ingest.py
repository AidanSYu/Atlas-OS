"""
Ingestion Service - Process documents through the knowledge layer.

Pipeline:
1. Extract text from PDFs
2. Chunk documents
3. Store chunks in PostgreSQL
4. Embed and index in Qdrant (with node_id references)
5. Extract entities and create graph nodes/edges
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import json
import uuid
from pypdf import PdfReader
import ollama
from sqlalchemy.orm import Session

from app.core.database import get_session, Node, Edge, Document, DocumentChunk
from app.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from datetime import datetime
import hashlib


class IngestionService:
    """Orchestrates document ingestion across all knowledge layers."""
    
    def __init__(self):
        self.session: Session = get_session()
        self.qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.collection_name = settings.QDRANT_COLLECTION
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        collections = self.qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            # Get embedding dimension from Ollama
            test_embedding = self._embed_text("test")
            dimension = len(test_embedding)
            
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE
                )
            )
    
    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using Ollama."""
        response = ollama.embeddings(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            prompt=text
        )
        return response['embedding']
    
    def _calculate_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def ingest_document(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Main ingestion pipeline.
        
        Returns:
            Summary of ingestion with statistics
        """
        try:
            # 1. Check for duplicate or add document
            file_hash = self._calculate_hash(file_path)
            file_size = Path(file_path).stat().st_size
            
            existing_doc = self.session.query(Document).filter(
                Document.file_hash == file_hash
            ).first()
            
            if existing_doc:
                return {
                    "status": "duplicate",
                    "doc_id": str(existing_doc.id),
                    "message": f"Document already exists as {existing_doc.filename}"
                }
            
            # Create new document
            doc_id = uuid.uuid4()
            document = Document(
                id=doc_id,
                filename=filename,
                file_hash=file_hash,
                file_path=file_path,
                file_size=file_size,
                mime_type="application/pdf",
                status="processing",
                uploaded_at=datetime.utcnow()
            )
            self.session.add(document)
            self.session.commit()
            
            # 2. Extract text from PDF
            pages = self._extract_pdf_text(file_path)
            
            # 3. Chunk document
            chunks = self._chunk_document(pages, doc_id, filename)
            
            # 4. Store chunks in PostgreSQL
            chunk_objects = []
            for chunk_data in chunks:
                chunk_obj = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc_id,
                    text=chunk_data["text"],
                    chunk_index=chunk_data["chunk_index"],
                    page_number=chunk_data.get("page_number"),
                    start_char=chunk_data.get("start_char"),
                    end_char=chunk_data.get("end_char"),
                    chunk_metadata=chunk_data.get("metadata", {})
                )
                chunk_objects.append(chunk_obj)
                self.session.add(chunk_obj)
            self.session.commit()
            
            # 5. Extract entities and create graph nodes
            node_ids_by_chunk = {}
            for chunk_idx, chunk in enumerate(chunks[:10]):  # Process first 10 chunks
                entities = self._extract_entities_from_text(
                    chunk["text"],
                    doc_id,
                    chunk["chunk_index"],
                    chunk["page_number"]
                )
                
                chunk_node_ids = []
                entity_nodes = []  # Track nodes for relationship creation
                
                for entity in entities:
                    # Create node
                    node_id = uuid.uuid4()
                    node = Node(
                        id=node_id,
                        label=entity.get("type", "Entity"),
                        properties={
                            "name": entity["name"],
                            "description": entity.get("description", ""),
                            "document_id": str(doc_id),
                            "chunk_id": f"{doc_id}_chunk_{chunk['chunk_index']}",
                            "page_number": chunk["page_number"],
                            "confidence": entity.get("confidence", 0.8)
                        }
                    )
                    self.session.add(node)
                    chunk_node_ids.append(str(node_id))
                    entity_nodes.append(node)  # Keep reference for relationships
                
                if chunk_node_ids:
                    node_ids_by_chunk[chunk["chunk_index"]] = chunk_node_ids
                
                # Create relationships between entities in same chunk
                if len(entity_nodes) > 1:
                    for i, node1 in enumerate(entity_nodes):
                        for node2 in entity_nodes[i+1:]:
                            edge = Edge(
                                source_id=node1.id,
                                target_id=node2.id,
                                type="CO_OCCURS",
                                properties={
                                    "document_id": str(doc_id),
                                    "chunk_id": f"{doc_id}_chunk_{chunk['chunk_index']}",
                                    "context": chunk["text"][:200]
                                }
                            )
                            self.session.add(edge)
            
            self.session.commit()
            
            # 6. Embed and store in Qdrant (with node_id references)
            vector_points = []
            for chunk_idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{chunk['chunk_index']}"
                embedding = self._embed_text(chunk["text"])
                
                # Include node_ids in metadata if available
                metadata = chunk.get("metadata", {})
                if chunk["chunk_index"] in node_ids_by_chunk:
                    metadata["node_ids"] = node_ids_by_chunk[chunk["chunk_index"]]
                
                point = PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload={
                        "chunk_id": chunk_id,
                        "doc_id": str(doc_id),
                        "text": chunk["text"],
                        "metadata": metadata
                    }
                )
                vector_points.append(point)
            
            if vector_points:
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=vector_points
                )
            
            # 7. Mark as completed
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            self.session.commit()
            
            return {
                "status": "success",
                "doc_id": str(doc_id),
                "filename": filename,
                "stats": {
                    "pages": len(pages),
                    "chunks": len(chunks),
                    "nodes": sum(len(ids) for ids in node_ids_by_chunk.values())
                }
            }
            
        except Exception as e:
            if 'doc_id' in locals():
                document.status = "failed"
                self.session.commit()
            return {
                "status": "failed",
                "error": str(e),
                "filename": filename
            }
    
    def _extract_pdf_text(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract text from PDF with page numbers."""
        reader = PdfReader(file_path)
        pages = []
        
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text.strip():
                pages.append({
                    "page_number": page_num,
                    "text": text,
                    "char_count": len(text)
                })
        
        return pages
    
    def _chunk_document(
        self,
        pages: List[Dict[str, Any]],
        doc_id: uuid.UUID,
        filename: str
    ) -> List[Dict[str, Any]]:
        """Chunk document with overlap."""
        chunks = []
        chunk_index = 0
        
        for page in pages:
            text = page["text"]
            page_num = page["page_number"]
            
            start = 0
            while start < len(text):
                end = start + settings.CHUNK_SIZE
                chunk_text = text[start:end]
                
                # Try to break at sentence boundary
                if end < len(text):
                    last_period = chunk_text.rfind('.')
                    last_newline = chunk_text.rfind('\n')
                    break_point = max(last_period, last_newline)
                    
                    if break_point > settings.CHUNK_SIZE * 0.5:
                        end = start + break_point + 1
                        chunk_text = text[start:end]
                
                chunks.append({
                    "text": chunk_text.strip(),
                    "chunk_index": chunk_index,
                    "page_number": page_num,
                    "start_char": start,
                    "end_char": end,
                    "metadata": {
                        "filename": filename,
                        "doc_id": str(doc_id),
                        "page": page_num
                    }
                })
                
                chunk_index += 1
                start = end - settings.CHUNK_OVERLAP
        
        return chunks
    
    def _extract_entities_from_text(
        self,
        text: str,
        doc_id: uuid.UUID,
        chunk_index: int,
        page_number: int
    ) -> List[Dict[str, Any]]:
        """Use LLM to extract entities from text."""
        prompt = f"""Extract key entities from this scientific text. Focus on:
- Chemicals, compounds, materials
- Experiments, procedures, methods
- Measurements, results, values
- Concepts, theories

For each entity, provide:
1. name (the entity name)
2. type (one of: chemical, experiment, measurement, concept, other)
3. description (brief 1-sentence description)

Text:
{text[:1500]}

Return ONLY a JSON array of entities, like:
[{{"name": "benzene", "type": "chemical", "description": "aromatic hydrocarbon"}}]

If no significant entities, return empty array: []
"""
        
        try:
            response = ollama.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                options={"temperature": 0.1}
            )
            
            response_text = response['response'].strip()
            
            # Try to find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                entities = json.loads(json_str)
                
                # Validate and clean
                valid_entities = []
                for ent in entities:
                    if isinstance(ent, dict) and "name" in ent and "type" in ent:
                        valid_entities.append({
                            "name": ent["name"],
                            "type": ent["type"],
                            "description": ent.get("description", ""),
                            "confidence": 0.8
                        })
                
                return valid_entities
            else:
                return []
            
        except Exception as e:
            # Fallback: simple regex extraction
            return self._fallback_entity_extraction(text)
    
    def _fallback_entity_extraction(self, text: str) -> List[Dict[str, Any]]:
        """Simple fallback entity extraction using regex."""
        pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        matches = re.findall(pattern, text)
        unique_entities = list(set(matches))[:10]
        
        return [
            {
                "name": entity,
                "type": "concept",
                "description": f"Extracted from text",
                "confidence": 0.5
            }
            for entity in unique_entities
        ]
