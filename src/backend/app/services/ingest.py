"""
Ingestion Service - Process documents through the knowledge layer.

Pipeline:
1. Extract text from documents (PDFs, DOCX, TXT, etc.)
2. Chunk documents
3. Store chunks in SQLite
4. Embed and index in Qdrant (embedded, in-process)
5. Extract entities and create graph nodes/edges

Production Desktop Sidecar: SQLite + embedded Qdrant + bundled LLMs.
"""
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
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

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from sqlalchemy.orm import Session

from app.core.database import get_session, Node, Edge, Document, DocumentChunk
from app.core.config import settings
from app.services.llm import LLMService
from app.core.qdrant_store import get_qdrant_client
from app.services.docling_parser import DoclingParser
from app.services.semantic_chunker import SemanticChunker
from app.services.raptor import RaptorService
from qdrant_client.models import Distance, VectorParams, PointStruct
from datetime import datetime
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates document ingestion across all knowledge layers."""

    def __init__(self):
        self.llm_service = LLMService.get_instance()

        # Embedded Qdrant - shared singleton (no server needed)
        self.qdrant_client = get_qdrant_client()
        self.collection_name = settings.QDRANT_COLLECTION

        # Thread pool for CPU-bound operations (PDF parsing, etc.)
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Initialize GLiNER
        self.gliner_model = self._load_gliner_model()
        if self.gliner_model is None:
            raise RuntimeError(
                "GLiNER model is required for ingestion. Fix the model install/config and retry."
            )

        # Phase B2: Docling VLM parser (lazy-loaded, optional)
        self.docling_parser = None
        if settings.USE_DOCLING and DoclingParser.is_available():
            self.docling_parser = DoclingParser.get_instance()
            logger.info("Docling VLM parser enabled")

        # Phase B3: Semantic chunker (optional)
        self.semantic_chunker = None
        if settings.USE_SEMANTIC_CHUNKING and SemanticChunker.is_available():
            self.semantic_chunker = SemanticChunker(max_tokens=settings.SEMANTIC_CHUNK_TOKENS)
            logger.info("Semantic chunker enabled")

        # Phase B4: RAPTOR hierarchy builder (optional)
        self.raptor = None
        if settings.USE_RAPTOR and RaptorService.is_available():
            self.raptor = RaptorService(self.llm_service)
            logger.info("RAPTOR hierarchy builder enabled")

        logger.info("IngestionService initialized (embedded Qdrant + SQLite)")

    def _load_gliner_model(self):
        """Load GLiNER: try ONNX if available, else PyTorch."""
        from gliner import GLiNER

        gliner_path = Path(settings.MODELS_DIR) / "gliner_small-v2.1"
        onnx_path = gliner_path / "model.onnx"

        if onnx_path.exists():
            try:
                model = GLiNER.from_pretrained(str(gliner_path), load_onnx_model=True)
                logger.info(f"Loaded GLiNER ONNX model from {gliner_path}")
                return model
            except Exception as e:
                logger.warning(f"GLiNER ONNX load failed ({e}), falling back to PyTorch")

        try:
            if gliner_path.exists():
                model = GLiNER.from_pretrained(str(gliner_path))
                logger.info(f"Loaded GLiNER model from {gliner_path}")
            else:
                logger.warning(f"GLiNER model not found at {gliner_path}, downloading...")
                model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
                logger.info("Loaded GLiNER model from HuggingFace")
            return model
        except Exception as e:
            logger.error(f"GLiNER entity extraction unavailable: {e}")
            return None

    async def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        collections = self.qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            dimension = self.llm_service.embedding_dimension
            logger.info(f"Creating Qdrant collection with dimension {dimension}")
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )

    async def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using bundled LLM service."""
        return await self.llm_service.embed(text)

    def _calculate_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_file_type_and_mime(self, filename: str) -> Tuple[str, str]:
        """
        Determine file type and MIME type from filename.
        
        Returns:
            Tuple of (file_type, mime_type)
        """
        lower_filename = filename.lower()
        
        if lower_filename.endswith('.pdf'):
            return ('pdf', 'application/pdf')
        elif lower_filename.endswith('.docx'):
            return ('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        elif lower_filename.endswith('.doc'):
            return ('doc', 'application/msword')
        elif lower_filename.endswith('.txt'):
            return ('txt', 'text/plain')
        else:
            # Default to text for unknown extensions
            return ('unknown', 'text/plain')

    async def ingest_document(
        self, file_path: str, filename: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main ingestion pipeline.

        Args:
            file_path: Path to the document file
            filename: Original filename
            project_id: Optional project to scope this document to

        Returns:
            Summary of ingestion with statistics
        """
        session = get_session()
        doc_id = None
        document = None
        start_time = time.time()
        try:
            logger.info(f"Starting ingestion pipeline for: {filename}")

            # Determine file type and MIME type
            file_type, mime_type = self._get_file_type_and_mime(filename)

            # 1. Check for duplicate
            file_hash = self._calculate_hash(file_path)
            file_size = Path(file_path).stat().st_size

            dup_query = session.query(Document).filter(Document.file_hash == file_hash)
            if project_id:
                dup_query = dup_query.filter(Document.project_id == project_id)
            existing_doc = dup_query.first()

            if existing_doc:
                logger.info(f"Skipping duplicate: {filename}")
                return {
                    "status": "duplicate",
                    "doc_id": str(existing_doc.id),
                    "message": f"Document already exists as {existing_doc.filename}",
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
                status="processing",
                project_id=project_id,
                uploaded_at=datetime.utcnow(),
            )
            session.add(document)
            session.commit()
            logger.info(f"Document created: {filename} (ID: {doc_id})")

            # 2. Extract text from document
            pages = await self._extract_text_from_file(file_path, file_type)
            logger.info(f"Extracted {len(pages)} sections from {file_type.upper()} file")

            if len(pages) == 0:
                logger.warning(f"No text extracted from {file_type.upper()} file")
                document.status = "completed"
                document.processed_at = datetime.utcnow()
                document.total_chunks = 0
                document.processed_chunks = 0
                session.commit()
                return {
                    "status": "completed",
                    "doc_id": doc_id,
                    "filename": filename,
                    "stats": {
                        "pages": 0,
                        "chunks": 0,
                        "nodes": 0,
                        "warning": f"No text extracted from document",
                    },
                }

            # 3. Chunk document
            chunks = self._chunk_document(pages, doc_id, filename)
            logger.info(f"Created {len(chunks)} chunks")

            document.total_chunks = len(chunks)
            document.processed_chunks = 0
            session.commit()

            # 4. Store chunks in SQLite
            for chunk_data in chunks:
                chunk_obj = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    text=chunk_data["text"],
                    chunk_index=chunk_data["chunk_index"],
                    page_number=chunk_data.get("page_number"),
                    start_char=chunk_data.get("start_char"),
                    end_char=chunk_data.get("end_char"),
                    chunk_metadata=chunk_data.get("metadata", {}),
                )
                session.add(chunk_obj)
            session.commit()
            logger.info(f"Stored {len(chunks)} chunks in SQLite")

            # 5. Ensure Qdrant collection exists
            await self._ensure_collection()

            # 6. Extract entities and create graph nodes
            node_ids_by_chunk = await self._extract_entities_parallel(
                chunks, doc_id, session, document, project_id
            )
            total_nodes = sum(len(ids) for ids in node_ids_by_chunk.values())
            logger.info(f"Created {total_nodes} knowledge graph nodes")
            session.commit()

            # 7. Embed and store in Qdrant
            vector_points = await self._embed_chunks_parallel(
                chunks, doc_id, node_ids_by_chunk, document, session
            )

            # 7.5: Build RAPTOR hierarchy (Phase B4)
            raptor_points = []
            if self.raptor and vector_points and len(vector_points) >= 3:
                try:
                    embeddings = [point.vector for point in vector_points]
                    hierarchy = await self.raptor.build_hierarchy(
                        chunks=chunks,
                        embeddings=embeddings,
                        doc_id=doc_id,
                        filename=filename,
                        n_clusters=min(settings.RAPTOR_CLUSTERS, len(chunks) // 3),
                    )

                    # Store L1 cluster summaries in Qdrant
                    for summary in hierarchy.get("L1", []):
                        if not summary.get("text") or not summary.get("embedding"):
                            continue
                        raptor_points.append(PointStruct(
                            id=str(uuid.uuid4()),
                            vector=summary["embedding"],
                            payload={
                                "chunk_id": str(uuid.uuid4()),
                                "doc_id": doc_id,
                                "text": summary["text"],
                                "metadata": summary["metadata"],
                            },
                        ))

                    # Store L2 document summary in Qdrant
                    l2 = hierarchy.get("L2")
                    if l2 and l2.get("text") and l2.get("embedding"):
                        raptor_points.append(PointStruct(
                            id=str(uuid.uuid4()),
                            vector=l2["embedding"],
                            payload={
                                "chunk_id": str(uuid.uuid4()),
                                "doc_id": doc_id,
                                "text": l2["text"],
                                "metadata": l2["metadata"],
                            },
                        ))

                    logger.info(f"RAPTOR: {len(raptor_points)} hierarchy vectors generated")
                except Exception as e:
                    logger.warning(f"RAPTOR hierarchy build failed (non-fatal): {e}")

            # 8. Upload all vectors to Qdrant (L0 chunks + RAPTOR L1/L2)
            all_points = vector_points + raptor_points
            if all_points:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self.executor,
                    lambda: self.qdrant_client.upsert(
                        collection_name=self.collection_name, points=all_points
                    ),
                )
                logger.info(f"Uploaded {len(all_points)} vectors to Qdrant ({len(vector_points)} chunks + {len(raptor_points)} RAPTOR)")

            # 9. Mark as completed
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            document.processed_chunks = document.total_chunks
            session.commit()

            elapsed = time.time() - start_time
            result = {
                "status": "success",
                "doc_id": doc_id,
                "filename": filename,
                "stats": {
                    "pages": len(pages),
                    "chunks": len(chunks),
                    "nodes": total_nodes,
                },
            }
            logger.info(f"Ingestion complete in {elapsed:.2f}s: {filename}")
            return result

        except Exception as e:
            logger.error(f"Ingestion failed for {filename}: {str(e)}", exc_info=True)
            try:
                session.rollback()
            except Exception:
                pass
            if document is not None:
                try:
                    document.status = "failed"
                    session.commit()
                except Exception:
                    try:
                        session.rollback()
                    except Exception:
                        pass
            return {"status": "failed", "error": str(e), "filename": filename}
        finally:
            session.close()

    # ----------------------------------------------------------------
    # Generic text extraction - dispatches based on file type
    # ----------------------------------------------------------------

    async def _extract_text_from_file(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """
        Extract text from document based on file type.
        
        Args:
            file_path: Path to the document file
            file_type: Type of file ('pdf', 'docx', 'doc', 'txt', etc.)
            
        Returns:
            List of dictionaries with extracted text and metadata
        """
        if file_type == 'pdf':
            return await self._extract_pdf_text(file_path)
        elif file_type == 'docx':
            return await self._extract_docx_text(file_path)
        elif file_type in ('doc', 'unknown'):
            # For .doc files, try DOCX first (many modern .doc files are actually .docx format)
            # Then fall back to txt extraction as a last resort
            try:
                return await self._extract_docx_text(file_path)
            except Exception as e:
                logger.warning(f"DOCX extraction failed for .doc file: {e}, treating as text")
                return await self._extract_txt_text(file_path)
        elif file_type == 'txt':
            return await self._extract_txt_text(file_path)
        else:
            logger.warning(f"Unknown file type: {file_type}, attempting text extraction")
            return await self._extract_txt_text(file_path)

    # ----------------------------------------------------------------
    # PDF extraction
    # ----------------------------------------------------------------

    async def _extract_pdf_text(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract text from PDF with page numbers (async).

        Phase B2: Tries Docling VLM parser first for structure-preserving
        extraction (tables, charts), falls back to pdfplumber/PyPDF.
        """
        # Phase B2: Try Docling first (preserves tables and structure)
        if self.docling_parser:
            try:
                loop = asyncio.get_event_loop()
                pages = await loop.run_in_executor(
                    self.executor,
                    self.docling_parser.parse_document,
                    file_path,
                )
                if pages:
                    logger.info(f"Docling extracted {len(pages)} pages")
                    return pages
            except Exception as e:
                logger.warning(f"Docling failed, falling back to pdfplumber: {e}")

        # Fallback: pdfplumber / PyPDF
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._extract_pdf_text_sync, file_path)

    def _extract_pdf_text_sync(self, file_path: str) -> List[Dict[str, Any]]:
        """Synchronous PDF text extraction."""
        pages = []

        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()
                        if text and text.strip():
                            pages.append({"page_number": page_num, "text": text, "char_count": len(text)})
                if pages:
                    return pages
            except Exception as e:
                logger.warning(f"pdfplumber extraction failed: {e}, trying PyPDF...")

        try:
            reader = PdfReader(file_path)
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text and text.strip():
                    pages.append({"page_number": page_num, "text": text, "char_count": len(text)})
        except Exception as e:
            logger.error(f"PyPDF extraction also failed: {e}")

        return pages

    # ----------------------------------------------------------------
    # DOCX extraction
    # ----------------------------------------------------------------

    async def _extract_docx_text(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract text from DOCX file (async wrapper)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._extract_docx_text_sync, file_path)

    def _extract_docx_text_sync(self, file_path: str) -> List[Dict[str, Any]]:
        """Synchronous DOCX text extraction."""
        pages = []
        
        if not DOCX_AVAILABLE:
            logger.error("python-docx not available. Install it to process DOCX files.")
            return pages
        
        try:
            doc = DocxDocument(file_path)
            full_text = ""
            
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text += para.text + "\n"
            
            # Also extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            full_text += cell.text + "\n"
            
            if full_text.strip():
                # Treat entire DOCX as one page for consistency
                pages.append({"page_number": 1, "text": full_text.strip(), "char_count": len(full_text)})
            
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
        
        return pages

    # ----------------------------------------------------------------
    # TXT extraction
    # ----------------------------------------------------------------

    async def _extract_txt_text(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract text from TXT file (async wrapper)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._extract_txt_text_sync, file_path)

    def _extract_txt_text_sync(self, file_path: str) -> List[Dict[str, Any]]:
        """Synchronous TXT text extraction."""
        pages = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if text.strip():
                # Treat entire text file as one page
                pages.append({"page_number": 1, "text": text.strip(), "char_count": len(text)})
        except UnicodeDecodeError:
            # Try with a different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    text = f.read()
                
                if text.strip():
                    pages.append({"page_number": 1, "text": text.strip(), "char_count": len(text)})
            except Exception as e:
                logger.error(f"TXT extraction with fallback encoding failed: {e}")
        except Exception as e:
            logger.error(f"TXT extraction failed: {e}")
        
        return pages

    # ----------------------------------------------------------------
    # Chunking
    # ----------------------------------------------------------------

    def _chunk_document(
        self, pages: List[Dict[str, Any]], doc_id: str, filename: str
    ) -> List[Dict[str, Any]]:
        """Chunk document using semantic or fixed-size strategy.

        Phase B3: Uses semantic chunker if available, otherwise falls back
        to the original fixed-size overlap chunking.
        """
        if self.semantic_chunker:
            try:
                chunks = self.semantic_chunker.chunk_pages(pages, doc_id, filename)
                if chunks:
                    logger.info(f"Semantic chunking produced {len(chunks)} chunks")
                    return chunks
            except Exception as e:
                logger.warning(f"Semantic chunking failed, falling back to fixed-size: {e}")

        return self._chunk_document_fixed_size(pages, doc_id, filename)

    def _chunk_document_fixed_size(
        self, pages: List[Dict[str, Any]], doc_id: str, filename: str
    ) -> List[Dict[str, Any]]:
        """Original fixed-size chunking with overlap (fallback)."""
        chunks = []
        chunk_index = 0

        for page in pages:
            text = page["text"]
            page_num = page["page_number"]
            start = 0
            while start < len(text):
                end = start + settings.CHUNK_SIZE
                chunk_text = text[start:end]

                if end < len(text):
                    last_period = chunk_text.rfind(".")
                    last_newline = chunk_text.rfind("\n")
                    break_point = max(last_period, last_newline)
                    if break_point > settings.CHUNK_SIZE * 0.5:
                        end = start + break_point + 1
                        chunk_text = text[start:end]

                chunks.append(
                    {
                        "text": chunk_text.strip(),
                        "chunk_index": chunk_index,
                        "page_number": page_num,
                        "start_char": start,
                        "end_char": end,
                        "metadata": {"filename": filename, "doc_id": doc_id, "page": page_num},
                    }
                )
                chunk_index += 1
                start = end - settings.CHUNK_OVERLAP

        return chunks

    # ----------------------------------------------------------------
    # Entity extraction
    # ----------------------------------------------------------------

    async def _extract_entities_parallel(
        self,
        chunks: List[Dict[str, Any]],
        doc_id: str,
        session: Session,
        document: Document,
        project_id: Optional[str] = None,
    ) -> Dict[int, List[str]]:
        """Extract entities from all chunks in parallel."""
        node_ids_by_chunk: Dict[int, List[str]] = {}
        entity_labels = [
            "Person", "Organization", "Location", "Concept",
            "Method", "Chemical", "Date", "Event", "Work",
            "Title", "Institution",
        ]

        extraction_tasks = []
        for chunk in chunks:
            task = self._extract_entities_gliner(chunk["text"], labels=entity_labels)
            extraction_tasks.append((chunk, task))

        results = await asyncio.gather(
            *[task for _, task in extraction_tasks], return_exceptions=True
        )

        processed_count = 0
        for (chunk, _), entities_or_error in zip(extraction_tasks, results):
            if isinstance(entities_or_error, Exception):
                logger.error(f"Entity extraction failed for chunk {chunk['chunk_index']}: {entities_or_error}")
                raise entities_or_error

            entities = entities_or_error
            chunk_uuid = str(uuid.uuid5(uuid.UUID(doc_id), f"chunk-{chunk['chunk_index']}"))

            chunk_node_ids: List[str] = []
            entity_nodes = []

            for entity in entities:
                node_id = str(uuid.uuid4())
                node = Node(
                    id=node_id,
                    label=entity.get("type", "Entity"),
                    document_id=doc_id,
                    project_id=project_id,
                    properties={
                        "name": entity["name"],
                        "description": entity.get("description", ""),
                        "chunk_id": chunk_uuid,
                        "page_number": chunk["page_number"],
                        "confidence": entity.get("confidence", 0.8),
                    },
                )
                session.add(node)
                chunk_node_ids.append(node_id)
                entity_nodes.append(node)

            if chunk_node_ids:
                node_ids_by_chunk[chunk["chunk_index"]] = chunk_node_ids

            # Create co-occurrence edges
            if len(entity_nodes) > 1:
                for i, node1 in enumerate(entity_nodes):
                    for node2 in entity_nodes[i + 1 :]:
                        edge = Edge(
                            id=str(uuid.uuid4()),
                            source_id=node1.id,
                            target_id=node2.id,
                            type="CO_OCCURS",
                            document_id=doc_id,
                            project_id=project_id,
                            properties={"chunk_id": chunk_uuid, "context": chunk["text"][:200]},
                        )
                        session.add(edge)

            processed_count += 1
            # Update progress more frequently for better UX
            # Calculate optimal update frequency based on total chunks (at least every 3 chunks or 10%)
            update_frequency = max(3, len(chunks) // 10) if chunks else 1
            if processed_count % update_frequency == 0 or processed_count == len(chunks):
                try:
                    session.refresh(document)
                    document.processed_chunks = processed_count
                    session.commit()
                    if processed_count % (update_frequency * 2) == 0 or processed_count == len(chunks):
                        logger.info(f"Entity extraction progress: {processed_count}/{len(chunks)} chunks")
                except Exception as e:
                    logger.warning(f"Failed to update progress: {e}")
                    session.rollback()

        return node_ids_by_chunk

    async def _embed_chunks_parallel(
        self,
        chunks: List[Dict[str, Any]],
        doc_id: str,
        node_ids_by_chunk: Dict[int, List[str]],
        document: Document,
        session: Session,
    ) -> List[PointStruct]:
        """Embed all chunks using batch processing (faster & thread-safe)."""
        if not chunks:
            return []
            
        texts = [chunk["text"] for chunk in chunks]
        
        try:
            # Use batch embedding instead of individual calls
            embeddings = await self.llm_service.embed_batch(texts)
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            raise

        vector_points = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_uuid = str(uuid.uuid5(uuid.UUID(doc_id), f"chunk-{chunk['chunk_index']}"))

            metadata = chunk.get("metadata", {})
            if chunk["chunk_index"] in node_ids_by_chunk:
                metadata["node_ids"] = node_ids_by_chunk[chunk["chunk_index"]]

            point = PointStruct(
                id=chunk_uuid,
                vector=embedding,
                payload={
                    "chunk_id": chunk_uuid,
                    "doc_id": doc_id,
                    "text": chunk["text"],
                    "metadata": metadata,
                },
            )
            vector_points.append(point)

        # Update progress at the end (since batch is all-or-nothing efficiently)
        try:
            session.refresh(document)
            document.processed_chunks = len(chunks)
            session.commit()
            logger.info(f"Embedding progress: {len(chunks)}/{len(chunks)} chunks (batch)")
        except Exception as e:
            logger.warning(f"Failed to update progress: {e}")
            session.rollback()

        return vector_points

    async def _extract_entities_gliner(
        self, text: str, labels: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract entities using GLiNER model."""
        if labels is None:
            labels = [
                "Person", "Organization", "Location", "Concept",
                "Method", "Chemical", "Date", "Event", "Work",
                "Title", "Institution",
            ]

        if self.gliner_model is None:
            raise RuntimeError("GLiNER model not available")

        try:
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
                        self.gliner_model.predict_entities(window_text, labels=labels, threshold=0.2)
                    )
                return all_preds

            predictions = await loop.run_in_executor(self.executor, _predict_all)

            entities = []
            seen_entities = set()
            type_mapping = {
                "Person": "person", "Organization": "organization", "Location": "location",
                "Concept": "concept", "Method": "method", "Chemical": "chemical",
                "Date": "date", "Event": "event", "Work": "work",
                "Title": "title", "Institution": "institution",
            }

            for pred in predictions:
                entity_name = pred.get("text", "").strip()
                entity_type = pred.get("label", "Concept")
                confidence = pred.get("score", 0.5)

                if not entity_name or len(entity_name) < 2:
                    continue

                entity_key = (entity_name.lower(), entity_type)
                if entity_key in seen_entities:
                    continue
                seen_entities.add(entity_key)

                entities.append(
                    {
                        "name": entity_name,
                        "type": type_mapping.get(entity_type, "concept"),
                        "description": "",
                        "confidence": float(confidence),
                    }
                )

            return entities

        except Exception as e:
            logger.error(f"GLiNER extraction failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"GLiNER entity extraction failed: {str(e)}") from e
