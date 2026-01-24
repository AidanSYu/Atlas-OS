"""
Ingestion Pipeline - Process documents through the knowledge layer.

This pipeline:
1. Extracts text from PDFs
2. Chunks documents
3. Stores in document store
4. Embeds and indexes in vector store
5. Extracts entities and relationships for knowledge graph

IDEMPOTENT: Can be run multiple times on same document without issues.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import json
from pypdf import PdfReader
import ollama
from document_store import DocumentStore
from vector_store import VectorStore
from knowledge_graph import KnowledgeGraph
from config import settings
from datetime import datetime
import sys

class IngestionPipeline:
    """Orchestrates document ingestion across all knowledge layers."""
    
    def __init__(self):
        self.doc_store = DocumentStore()
        self.vector_store = VectorStore()
        self.knowledge_graph = KnowledgeGraph()
    
    def ingest_document(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Main ingestion pipeline - processes document through all layers.
        
        Returns:
            Summary of ingestion with statistics
        """
        try:
            # 1. Add to document store
            file_size = Path(file_path).stat().st_size
            doc_result = self.doc_store.add_document(
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type="application/pdf"
            )
            
            if doc_result["status"] == "duplicate":
                return doc_result
            
            doc_id = doc_result["doc_id"]
            
            # Update status
            self.doc_store.update_document_status(doc_id, "processing")
            
            # 2. Extract text from PDF
            pages = self._extract_pdf_text(file_path)
            
            # 3. Chunk document
            chunks = self._chunk_document(pages, doc_id, filename)
            
            # 4. Store chunks in document store
            chunk_ids = self.doc_store.add_chunks(doc_id, chunks)
            
            # 5. Embed and store in vector store
            vector_chunks = self._prepare_vector_chunks(chunks, doc_id, filename)
            self.vector_store.add_chunks(vector_chunks)
            
            # 6. Extract entities and build knowledge graph
            entities_count = self._extract_and_store_entities(chunks, doc_id, filename)
            
            # 7. Mark as completed
            self.doc_store.update_document_status(doc_id, "completed")
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "filename": filename,
                "stats": {
                    "pages": len(pages),
                    "chunks": len(chunks),
                    "entities": entities_count
                }
            }
            
        except Exception as e:
            if 'doc_id' in locals():
                self.doc_store.update_document_status(doc_id, "failed")
            
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
        doc_id: str,
        filename: str
    ) -> List[Dict[str, Any]]:
        """
        Chunk document with overlap.
        
        Uses simple character-based chunking with overlap.
        Each chunk tracks its source page.
        """
        chunks = []
        chunk_index = 0
        
        for page in pages:
            text = page["text"]
            page_num = page["page_number"]
            
            # Simple character-based chunking
            start = 0
            while start < len(text):
                end = start + settings.CHUNK_SIZE
                chunk_text = text[start:end]
                
                # Try to break at sentence boundary
                if end < len(text):
                    last_period = chunk_text.rfind('.')
                    last_newline = chunk_text.rfind('\n')
                    break_point = max(last_period, last_newline)
                    
                    if break_point > settings.CHUNK_SIZE * 0.5:  # At least 50% of chunk
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
                        "doc_id": doc_id,
                        "page": page_num
                    }
                })
                
                chunk_index += 1
                start = end - settings.CHUNK_OVERLAP  # Overlap
        
        return chunks
    
    def _prepare_vector_chunks(
        self,
        chunks: List[Dict[str, Any]],
        doc_id: str,
        filename: str
    ) -> List[Dict[str, Any]]:
        """Prepare chunks for vector store."""
        vector_chunks = []
        
        for chunk in chunks:
            vector_chunks.append({
                "chunk_id": f"{doc_id}_chunk_{chunk['chunk_index']}",
                "text": chunk["text"],
                "doc_id": doc_id,
                "metadata": {
                    "filename": filename,
                    "page": chunk["page_number"],
                    "chunk_index": chunk["chunk_index"]
                }
            })
        
        return vector_chunks
    
    def _extract_and_store_entities(
        self,
        chunks: List[Dict[str, Any]],
        doc_id: str,
        filename: str
    ) -> int:
        """
        Extract entities using LLM and store in knowledge graph.
        
        Returns count of entities extracted.
        """
        total_entities = 0
        print(f"[INGEST] Starting entity extraction for {len(chunks)} chunks", file=sys.stderr)
        
        # Process each chunk for entity extraction
        for chunk_idx, chunk in enumerate(chunks[:5]):  # Process first 5 chunks for faster testing
            try:
                entities = self._extract_entities_from_text(
                    chunk["text"],
                    doc_id,
                    chunk["chunk_index"],
                    chunk["page_number"]
                )
                
                print(f"[INGEST] Chunk {chunk_idx}: Extracted {len(entities)} entities", file=sys.stderr)
                
                # Store entities and relationships
                entity_ids = {}
                
                for entity in entities:
                    entity_id = self.knowledge_graph.add_entity(
                        name=entity["name"],
                        entity_type=entity["type"],
                        document_id=doc_id,
                        chunk_id=f"{doc_id}_chunk_{chunk['chunk_index']}",
                        page_number=chunk["page_number"],
                        description=entity.get("description"),
                        confidence=entity.get("confidence", 0.8)
                    )
                    entity_ids[entity["name"]] = entity_id
                    total_entities += 1
                    print(f"[INGEST] Added entity: {entity['name']} ({entity['type']})", file=sys.stderr)
                
                # Create relationships between entities in same chunk
                entity_list = list(entity_ids.keys())
                for i, entity1 in enumerate(entity_list):
                    for entity2 in entity_list[i+1:]:
                        self.knowledge_graph.add_relationship(
                            source_id=entity_ids[entity1],
                            target_id=entity_ids[entity2],
                            relationship_type="co-occurs",
                            context=chunk["text"][:200],  # First 200 chars as context
                            document_id=doc_id,
                            confidence=0.7
                        )
                
            except Exception as e:
                print(f"[INGEST] Error extracting entities from chunk {chunk['chunk_index']}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                continue
        
        print(f"[INGEST] Total entities extracted: {total_entities}", file=sys.stderr)
        return total_entities
    
    def _extract_entities_from_text(
        self,
        text: str,
        doc_id: str,
        chunk_index: int,
        page_number: int
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to extract entities from text.
        
        Returns list of entities with name, type, and description.
        """
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
            print(f"[ENTITY-EXTRACT] Calling LLM for chunk {chunk_index}", file=sys.stderr)
            response = ollama.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                options={"temperature": 0.1}
            )
            
            # Parse JSON response
            response_text = response['response'].strip()
            print(f"[ENTITY-EXTRACT] LLM response (first 200 chars): {response_text[:200]}", file=sys.stderr)
            
            # Try to find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                print(f"[ENTITY-EXTRACT] Extracted JSON: {json_str}", file=sys.stderr)
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
                
                print(f"[ENTITY-EXTRACT] Valid entities found: {len(valid_entities)}", file=sys.stderr)
                return valid_entities
            else:
                print(f"[ENTITY-EXTRACT] No JSON array found in response", file=sys.stderr)
                return []
            
        except Exception as e:
            print(f"[ENTITY-EXTRACT] Error in entity extraction: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            # Fallback: simple regex extraction of capitalized terms
            return self._fallback_entity_extraction(text)
    
    def _fallback_entity_extraction(self, text: str) -> List[Dict[str, Any]]:
        """Simple fallback entity extraction using regex."""
        # Extract capitalized phrases (likely entities)
        pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        matches = re.findall(pattern, text)
        
        # Deduplicate and limit
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
