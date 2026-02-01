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
import logging
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
from pypdf import PdfReader
from ollama import AsyncClient
from sqlalchemy.orm import Session

from app.core.database import get_session, Node, Edge, Document, DocumentChunk
from app.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from datetime import datetime
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates document ingestion across all knowledge layers."""
    
    def __init__(self):
        # Initialize Ollama async client for GPU-bound operations
        self.ollama_client = AsyncClient(host=settings.OLLAMA_BASE_URL)
        self.qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.collection_name = settings.QDRANT_COLLECTION
        
        # Thread pool for CPU-bound operations (PDF parsing, etc.)
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize GLiNER model for entity extraction (required)
        try:
            from gliner import GLiNER
            self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
            logger.info("✅ Loaded GLiNER model 'urchade/gliner_small-v2.1' for NER")
        except Exception as e:
            logger.error(f"❌ GLiNER entity extraction unavailable: {e}")
            raise RuntimeError("GLiNER model is required for ingestion. Fix the model install/config and retry.") from e
        
        # Note: Async validation happens on first use
        # Collection setup happens on first use
    
    async def _validate_ollama_connection(self):
        """Validate Ollama connection and required models (async)."""
        try:
            # Test connection with a simple embedding
            logger.info(f"Testing Ollama connection to {settings.OLLAMA_BASE_URL}")
            test_response = await self.ollama_client.embeddings(
                model=settings.OLLAMA_EMBEDDING_MODEL,
                prompt="test connection"
            )
            logger.info("✅ Ollama embedding model connection successful")
            
            # Test generation model
            gen_response = await self.ollama_client.generate(
                model=settings.OLLAMA_MODEL,
                prompt="test",
                options={"temperature": 0.1}
            )
            logger.info("✅ Ollama generation model connection successful")
            
        except Exception as e:
            logger.error(f"❌ Ollama connection failed: {str(e)}")
            logger.error(f"Make sure Ollama is running and models '{settings.OLLAMA_MODEL}' and '{settings.OLLAMA_EMBEDDING_MODEL}' are installed")
            raise ConnectionError(f"Ollama connection failed: {str(e)}")
    
    async def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist (async)."""
        collections = self.qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            # Get embedding dimension from Ollama (async call)
            try:
                response = await self.ollama_client.embeddings(
                    model=settings.OLLAMA_EMBEDDING_MODEL,
                    prompt="test"
                )
                dimension = len(response['embedding'])
            except Exception as e:
                logger.warning(f"Failed to get embedding dimension, using default 768: {e}")
                dimension = 768  # Default for nomic-embed-text
            
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE
                )
            )
    
    async def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using Ollama (async, GPU-bound)."""
        # Direct async call - Ollama server handles GPU utilization
        response = await self.ollama_client.embeddings(
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
    
    async def ingest_document(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Main ingestion pipeline.
        
        Returns:
            Summary of ingestion with statistics
        """
        session = get_session()
        doc_id = None
        document = None
        start_time = time.time()
        try:
            logger.info(f"🔄 Starting ingestion pipeline for: {filename}")
            
            # 1. Check for duplicate or add document
            file_hash = self._calculate_hash(file_path)
            file_size = Path(file_path).stat().st_size
            
            existing_doc = session.query(Document).filter(
                Document.file_hash == file_hash
            ).first()
            
            if existing_doc:
                logger.info(f"⏭️ Skipping duplicate: {filename} (already ingested)")
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
            session.add(document)
            session.commit()
            logger.info(f"📄 Document created: {filename} (ID: {doc_id})")
            
            # 2. Extract text from PDF
            logger.info(f"📖 Extracting text from PDF...")
            pages = await self._extract_pdf_text(file_path)
            logger.info(f"✅ Extracted {len(pages)} pages from PDF")
            
            if len(pages) == 0:
                logger.warning(f"⚠️  No text extracted from PDF! The PDF may be scanned images or have extraction restrictions.")
                # Mark as completed but with warning
                document.status = "completed"
                document.processed_at = datetime.utcnow()
                document.total_chunks = 0
                document.processed_chunks = 0
                session.commit()
                return {
                    "status": "completed",
                    "doc_id": str(doc_id),
                    "filename": filename,
                    "stats": {
                        "pages": 0,
                        "chunks": 0,
                        "nodes": 0,
                        "warning": "No text extracted - PDF may be scanned images"
                    }
                }
            
            # 3. Chunk document
            logger.info(f"✂️ Chunking document into segments...")
            chunks = self._chunk_document(pages, doc_id, filename)
            logger.info(f"✅ Created {len(chunks)} chunks")
            
            # Set total chunks for progress tracking
            document.total_chunks = len(chunks)
            document.processed_chunks = 0
            session.commit()
            
            # 4. Store chunks in PostgreSQL
            logger.info(f"💾 Storing chunks in PostgreSQL...")
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
                session.add(chunk_obj)
            session.commit()
            logger.info(f"✅ Stored {len(chunks)} chunks in PostgreSQL")
            
            # 5. Ensure collection exists (async)
            logger.info(f"🗄️ Ensuring Qdrant collection exists...")
            await self._ensure_collection()
            logger.info(f"✅ Qdrant collection ready")
            
            # 6. Extract entities and create graph nodes (PARALLELIZED)
            logger.info(f"🔗 Extracting entities and creating knowledge graph nodes...")
            node_ids_by_chunk = await self._extract_entities_parallel(
                chunks, doc_id, session, document
            )
            total_nodes = sum(len(ids) for ids in node_ids_by_chunk.values())
            logger.info(f"✅ Created {total_nodes} knowledge graph nodes from {len(node_ids_by_chunk)} chunks with entities")
            
            session.commit()
            
            # 7. Embed and store in Qdrant (with node_id references) - PARALLELIZED (GPU-bound)
            logger.info(f"🧠 Embedding chunks with Ollama...")
            vector_points = await self._embed_chunks_parallel(chunks, doc_id, node_ids_by_chunk, document, session)
            logger.info(f"✅ Embedded {len(vector_points)} chunks")
            
            if vector_points:
                # Upsert is synchronous but fast, run in executor
                logger.info(f"📤 Uploading embeddings to Qdrant vector store...")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self.executor,
                    lambda: self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=vector_points
                    )
                )
                logger.info(f"✅ Uploaded {len(vector_points)} vectors to Qdrant")
            
            # 8. Mark as completed and ensure progress is 100%
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            document.processed_chunks = document.total_chunks
            session.commit()
            
            elapsed = time.time() - start_time
            result = {
                "status": "success",
                "doc_id": str(doc_id),
                "filename": filename,
                "stats": {
                    "pages": len(pages),
                    "chunks": len(chunks),
                    "nodes": sum(len(ids) for ids in node_ids_by_chunk.values())
                }
            }
            
            logger.info(f"✅ Ingestion complete in {elapsed:.2f}s: {filename}")
            logger.info(f"   Pages: {len(pages)}, Chunks: {len(chunks)}, Graph Nodes: {result['stats']['nodes']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ingestion failed for {filename}: {str(e)}", exc_info=True)
            # Rollback any uncommitted changes
            try:
                session.rollback()
            except Exception:
                pass
            
            # Update document status if it was created
            if document is not None:
                try:
                    document.status = "failed"
                    session.commit()
                except Exception:
                    try:
                        session.rollback()
                    except Exception:
                        pass
            
            return {
                "status": "failed",
                "error": str(e),
                "filename": filename
            }
        finally:
            session.close()
    
    async def _extract_pdf_text(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract text from PDF with page numbers (async)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._extract_pdf_text_sync,
            file_path
        )
    
    def _extract_pdf_text_sync(self, file_path: str) -> List[Dict[str, Any]]:
        """Synchronous PDF text extraction using pdfplumber (preferred) or PyPDF."""
        pages = []
        
        # Try pdfplumber first (better extraction)
        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()
                        if text and text.strip():
                            pages.append({
                                "page_number": page_num,
                                "text": text,
                                "char_count": len(text)
                            })
                if pages:
                    logger.info(f"✅ Extracted {len(pages)} pages using pdfplumber")
                    return pages
            except Exception as e:
                logger.warning(f"pdfplumber extraction failed: {e}, trying PyPDF...")
        
        # Fallback to PyPDF
        try:
            reader = PdfReader(file_path)
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text and text.strip():
                    pages.append({
                        "page_number": page_num,
                        "text": text,
                        "char_count": len(text)
                    })
            logger.info(f"✅ Extracted {len(pages)} pages using PyPDF")
        except Exception as e:
            logger.error(f"PyPDF extraction also failed: {e}")
        
        return pages
    
    def _chunk_document(
        self,
        pages: List[Dict[str, Any]],
        doc_id: uuid.UUID,
        filename: str
    ) -> List[Dict[str, Any]]:
        """Chunk document into overlapping segments."""
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
    
    async def _extract_entities_parallel(
        self,
        chunks: List[Dict[str, Any]],
        doc_id: uuid.UUID,
        session: Session,
        document: Document
    ) -> Dict[int, List[str]]:
        """Extract entities from all chunks in parallel."""
        node_ids_by_chunk = {}
        
        # Create tasks for parallel entity extraction
        extraction_tasks = []
        for chunk in chunks:
            task = self._extract_entities_gliner(
                chunk["text"],
                labels=[
                    "Person",
                    "Organization",
                    "Location",
                    "Concept",
                    "Method",
                    "Chemical",
                    "Date",
                    "Event",
                    "Work",
                    "Title",
                    "Institution"
                ]
            )
            extraction_tasks.append((chunk, task))
        
        # Execute all extractions in parallel
        results = await asyncio.gather(*[task for _, task in extraction_tasks], return_exceptions=True)
        
        # Process results and create nodes/edges
        processed_count = 0
        for (chunk, _), entities_or_error in zip(extraction_tasks, results):
            if isinstance(entities_or_error, Exception):
                logger.error(f"Entity extraction failed for chunk {chunk['chunk_index']}: {entities_or_error}")
                raise entities_or_error
            
            entities = entities_or_error
            chunk_uuid = uuid.uuid5(doc_id, f"chunk-{chunk['chunk_index']}")
            
            chunk_node_ids = []
            entity_nodes = []
            
            for entity in entities:
                # Create node
                node_id = uuid.uuid4()
                # PERFORMANCE FIX: Use new document_id FK instead of storing in JSONB
                node = Node(
                    id=node_id,
                    label=entity.get("type", "Entity"),
                    document_id=doc_id,  # Set explicit FK
                    properties={
                        "name": entity["name"],
                        "description": entity.get("description", ""),
                        "chunk_id": str(chunk_uuid),
                        "page_number": chunk["page_number"],
                        "confidence": entity.get("confidence", 0.8)
                    }
                )
                session.add(node)
                chunk_node_ids.append(str(node_id))
                entity_nodes.append(node)
            
            if chunk_node_ids:
                node_ids_by_chunk[chunk["chunk_index"]] = chunk_node_ids
            
            # Create relationships between entities in same chunk
            if len(entity_nodes) > 1:
                for i, node1 in enumerate(entity_nodes):
                    for node2 in entity_nodes[i+1:]:
                        # PERFORMANCE FIX: Use new document_id FK instead of storing in JSONB
                        edge = Edge(
                            source_id=node1.id,
                            target_id=node2.id,
                            type="CO_OCCURS",
                            document_id=doc_id,  # Set explicit FK
                            properties={
                                "chunk_id": str(chunk_uuid),
                                "context": chunk["text"][:200]
                            }
                        )
                        session.add(edge)
            
            # Update progress every 10 chunks
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == len(chunks):
                try:
                    session.refresh(document)
                    document.processed_chunks = min(processed_count, document.total_chunks)
                    session.commit()
                except Exception as e:
                    logger.warning(f"Failed to update progress: {e}")
                    session.rollback()
        
        return node_ids_by_chunk
    
    async def _embed_chunks_parallel(
        self,
        chunks: List[Dict[str, Any]],
        doc_id: uuid.UUID,
        node_ids_by_chunk: Dict[int, List[str]],
        document: Document,
        session: Session
    ) -> List[PointStruct]:
        """Embed all chunks in parallel."""
        # Create embedding tasks
        embedding_tasks = []
        for chunk in chunks:
            task = self._embed_text(chunk["text"])
            embedding_tasks.append((chunk, task))
        
        # Execute all embeddings in parallel
        embeddings = await asyncio.gather(*[task for _, task in embedding_tasks], return_exceptions=True)
        
        # Create vector points and update progress
        vector_points = []
        processed_count = 0
        for (chunk, _), embedding_or_error in zip(embedding_tasks, embeddings):
            if isinstance(embedding_or_error, Exception):
                logger.error(f"Embedding failed for chunk {chunk['chunk_index']}: {embedding_or_error}")
                continue
            
            embedding = embedding_or_error
            chunk_uuid = uuid.uuid5(doc_id, f"chunk-{chunk['chunk_index']}")
            chunk_id = str(chunk_uuid)
            
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
            
            # Update progress every 10 chunks
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == len(chunks):
                try:
                    session.refresh(document)
                    document.processed_chunks = min(processed_count, document.total_chunks)
                    session.commit()
                except Exception as e:
                    logger.warning(f"Failed to update progress: {e}")
                    session.rollback()
        
        return vector_points
    
    async def _extract_entities_gliner(
        self,
        text: str,
        labels: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract entities using GLiNER model.
        
        Args:
            text: Text to extract entities from
            labels: List of entity labels to extract (default: Person, Organization, Location, Concept, Method, Chemical)
        
        Returns:
            List of entity dictionaries with name, type, description, and confidence
        """
        if labels is None:
            labels = [
                "Person",
                "Organization",
                "Location",
                "Concept",
                "Method",
                "Chemical",
                "Date",
                "Event",
                "Work",
                "Title",
                "Institution"
            ]
        
        # Check if GLiNER is available
        if self.gliner_model is None:
            logger.error("GLiNER model is not loaded. Cannot extract entities.")
            raise RuntimeError("GLiNER model not available - entity extraction required")
        
        try:
            # Run GLiNER in executor (CPU-bound but fast)
            # Split large chunks into smaller windows to improve recall
            loop = asyncio.get_event_loop()
            window_size = 1200
            overlap = 150
            windows = []
            if len(text) <= window_size:
                windows = [text]
            else:
                start = 0
                while start < len(text):
                    end = min(len(text), start + window_size)
                    windows.append(text[start:end])
                    if end == len(text):
                        break
                    start = end - overlap

            def _predict_all():
                all_preds = []
                for window_text in windows:
                    all_preds.extend(
                        self.gliner_model.predict_entities(
                            window_text,
                            labels=labels,
                            threshold=0.2
                        )
                    )
                return all_preds

            predictions = await loop.run_in_executor(self.executor, _predict_all)
            
            # Convert GLiNER format to our internal format
            entities = []
            seen_entities = set()  # Deduplicate by name+type
            
            for pred in predictions:
                entity_name = pred.get("text", "").strip()
                entity_type = pred.get("label", "Concept")
                confidence = pred.get("score", 0.5)
                
                # Skip empty or very short entities
                if not entity_name or len(entity_name) < 2:
                    continue
                
                # Deduplicate
                entity_key = (entity_name.lower(), entity_type)
                if entity_key in seen_entities:
                    continue
                seen_entities.add(entity_key)
                
                # Map GLiNER labels to our internal types (lowercase for consistency)
                type_mapping = {
                    "Person": "person",
                    "Organization": "organization",
                    "Location": "location",
                    "Concept": "concept",
                    "Method": "method",
                    "Chemical": "chemical",
                    "Date": "date",
                    "Event": "event",
                    "Work": "work",
                    "Title": "title",
                    "Institution": "institution"
                }
                mapped_type = type_mapping.get(entity_type, "concept")
                
                entities.append({
                    "name": entity_name,
                    "type": mapped_type,
                    "description": "",  # GLiNER doesn't provide descriptions
                    "confidence": float(confidence)
                })
            
            return entities
            
        except Exception as e:
            logger.error(f"GLiNER extraction failed: {str(e)}", exc_info=True)
            # Re-raise to make errors visible
            raise RuntimeError(f"GLiNER entity extraction failed: {str(e)}") from e
    
