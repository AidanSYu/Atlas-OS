"""
Query Orchestrator - Coordinates retrieval across all knowledge layers.

This module:
1. Receives user queries
2. Retrieves from vector store (semantic search)
3. Expands context from knowledge graph (relationships)
4. Fetches supporting documents
5. Synthesizes answer using LLM
6. Explains reasoning with citations and relationship paths

The AI does not know things. It queries the knowledge substrate.
"""

from typing import List, Dict, Any, Optional
import ollama
from vector_store import VectorStore
from knowledge_graph import KnowledgeGraph
from document_store import DocumentStore
from config import settings
import re

class QueryOrchestrator:
    """Orchestrates query answering across the knowledge layer."""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.knowledge_graph = KnowledgeGraph()
        self.doc_store = DocumentStore()
    
    def answer_query(self, query: str) -> Dict[str, Any]:
        """
        Main query pipeline - orchestrates retrieval and reasoning.
        
        Returns:
            {
                "answer": str,
                "reasoning": str,
                "citations": List[Dict],
                "relationships": List[Dict],
                "context_sources": Dict
            }
        """
        # 1. Semantic retrieval from vector store - get MORE results for better context
        vector_results = self.vector_store.search(query, top_k=settings.TOP_K_RETRIEVAL + 5)  # Increased retrieval
        
        if not vector_results:
            return {
                "answer": "No relevant documents found to answer this query.",
                "reasoning": "Vector search returned no results.",
                "citations": [],
                "relationships": [],
                "context_sources": {
                    "vector_chunks": 0,
                    "graph_entities": 0,
                    "graph_relationships": 0,
                    "documents": 0
                }
            }
        
        # 2. Extract mentioned entities from query and results
        entities = self._extract_query_entities(query, vector_results)
        
        # 3. Expand context using knowledge graph
        graph_context = None
        if entities:
            graph_context = self.knowledge_graph.expand_context(entities, max_hops=2)
        
        # 4. Fetch supporting document metadata
        doc_ids = list(set([r["doc_id"] for r in vector_results]))
        documents = [self.doc_store.get_document(doc_id) for doc_id in doc_ids]
        documents = [d for d in documents if d is not None]
        
        # 5. Synthesize answer using LLM
        answer_data = self._synthesize_answer(query, vector_results, graph_context, documents)
        
        # 6. Format response with full context
        return {
            "answer": answer_data["answer"],
            "reasoning": answer_data["reasoning"],
            "citations": self._format_citations(vector_results[:10]),  # More citations
            "relationships": self._format_relationships(graph_context) if graph_context else [],
            "context_sources": {
                "vector_chunks": len(vector_results),
                "graph_entities": len(graph_context["entities"]) if graph_context else 0,
                "graph_relationships": len(graph_context["relationships"]) if graph_context else 0,
                "documents": len(documents)
            }
        }
    
    def find_relationship(self, entity1: str, entity2: str) -> Dict[str, Any]:
        """
        Find and explain how two entities are connected.
        
        Query type: "How are X and Y related?"
        """
        # Find paths in knowledge graph
        paths = self.knowledge_graph.find_path(entity1, entity2, max_depth=3)
        
        if not paths:
            return {
                "answer": f"No direct relationship found between {entity1} and {entity2} in the knowledge base.",
                "paths": [],
                "reasoning": "Searched knowledge graph but found no connecting paths."
            }
        
        # Format paths into human-readable explanations
        path_explanations = []
        for path in paths:
            explanation = self._explain_path(path)
            path_explanations.append(explanation)
        
        # Use LLM to synthesize explanation
        answer = self._synthesize_relationship_answer(entity1, entity2, path_explanations)
        
        return {
            "answer": answer,
            "paths": path_explanations,
            "reasoning": f"Found {len(paths)} connection path(s) in the knowledge graph."
        }
    
    def query_document(self, doc_id: str, question: str) -> Dict[str, Any]:
        """
        Answer questions about a specific document.
        
        Query type: "What does document X say about Y?"
        """
        # Get document info
        document = self.doc_store.get_document(doc_id)
        
        if not document:
            return {
                "answer": "Document not found.",
                "citations": [],
                "reasoning": "No document with that ID exists."
            }
        
        # Search within this document only
        vector_results = self.vector_store.search(question, top_k=5, doc_id=doc_id)
        
        # Get entities from this document
        entities = self.knowledge_graph.get_document_entities(doc_id)
        
        # Synthesize answer
        answer_data = self._synthesize_answer(
            question,
            vector_results,
            {"entities": entities, "relationships": []},
            [document]
        )
        
        return {
            "answer": answer_data["answer"],
            "document": document["filename"],
            "citations": self._format_citations(vector_results),
            "entities_mentioned": [e["name"] for e in entities[:10]],
            "reasoning": f"Searched {len(vector_results)} relevant chunks from {document['filename']}"
        }
    
    def find_documents_mentioning(self, concept: str) -> Dict[str, Any]:
        """
        Find all documents mentioning a concept.
        
        Query type: "Which documents mention X?"
        """
        # Search vector store
        vector_results = self.vector_store.search(concept, top_k=20)
        
        # Group by document
        doc_mentions = {}
        for result in vector_results:
            doc_id = result["doc_id"]
            if doc_id not in doc_mentions:
                doc = self.doc_store.get_document(doc_id)
                if doc:
                    doc_mentions[doc_id] = {
                        "document": doc,
                        "chunks": [],
                        "relevance": 0
                    }
            
            if doc_id in doc_mentions:
                doc_mentions[doc_id]["chunks"].append(result)
                doc_mentions[doc_id]["relevance"] += result["relevance_score"]
        
        # Sort by relevance
        sorted_docs = sorted(
            doc_mentions.values(),
            key=lambda x: x["relevance"],
            reverse=True
        )
        
        # Format answer
        doc_list = [
            {
                "filename": d["document"]["filename"],
                "doc_id": d["document"]["id"],
                "mentions": len(d["chunks"]),
                "relevance": d["relevance"]
            }
            for d in sorted_docs
        ]
        
        return {
            "answer": f"Found {len(doc_list)} documents mentioning '{concept}'",
            "documents": doc_list,
            "reasoning": f"Semantic search found {len(vector_results)} relevant chunks across documents."
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge layer statistics."""
        try:
            return {
                "vector_store": self.vector_store.get_stats(),
                "document_store": self.doc_store.get_stats(),
                "entity_types": self.knowledge_graph.get_entity_types()
            }
        except Exception as e:
            return {
                "vector_store": {"error": str(e)},
                "document_store": {"error": str(e)},
                "entity_types": []
            }
    
    # ===== PRIVATE METHODS =====
    
    def _extract_query_entities(
        self,
        query: str,
        vector_results: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract potential entity names from query and results."""
        entities = set()
        
        # Extract capitalized words from query (potential entities)
        query_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
        entities.update(query_entities)
        
        # Get entities from top result chunks
        for result in vector_results[:3]:
            text_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', result["text"])
            entities.update(text_entities[:5])  # Limit per chunk
        
        return list(entities)[:10]  # Limit total
    
    def _aggregate_document_context(
        self,
        vector_results: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group and organize chunks by document and page for better context.
        This maintains document flow and prevents scattered page-by-page output.
        """
        doc_context = {}
        
        for result in vector_results:
            metadata = result.get('metadata', {})
            doc_id = result.get('doc_id', 'unknown')
            doc_filename = metadata.get('filename', 'Unknown')
            page = metadata.get('page', 0)
            
            if doc_id not in doc_context:
                doc_context[doc_id] = {
                    'filename': doc_filename,
                    'pages': {}
                }
            
            if page not in doc_context[doc_id]['pages']:
                doc_context[doc_id]['pages'][page] = []
            
            doc_context[doc_id]['pages'][page].append(result)
        
        return doc_context
    
    def _build_context_narrative(
        self,
        vector_results: List[Dict[str, Any]],
        doc_context: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Build a coherent narrative context by organizing chunks logically.
        Instead of random chunks, groups by document and page for continuity.
        """
        context_parts = []
        
        # Sort documents and pages for coherent reading order
        for doc_id in sorted(doc_context.keys()):
            doc_info = doc_context[doc_id]
            context_parts.append(f"\n{'='*70}")
            context_parts.append(f"DOCUMENT: {doc_info['filename']}")
            context_parts.append(f"{'='*70}")
            
            # Sort pages in numerical order
            for page_num in sorted(doc_info['pages'].keys()):
                chunks = doc_info['pages'][page_num]
                
                # Merge closely related chunks from same page
                merged_text = "\n".join([chunk["text"] for chunk in chunks])
                
                # Remove excessive whitespace while preserving structure
                merged_text = "\n".join(line.strip() for line in merged_text.split("\n") if line.strip())
                
                context_parts.append(f"\n[Page {page_num}]")
                # Include more content but still be reasonable
                context_parts.append(merged_text[:1000])  # Increased from 500
        
        return "\n".join(context_parts)
    
    def _synthesize_answer(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        graph_context: Optional[Dict[str, Any]],
        documents: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Use LLM to synthesize answer from context with improved document integration."""
        
        # Aggregate documents for better context flow
        doc_context = self._aggregate_document_context(vector_results[:15])  # Increased from 5
        
        # Build coherent context narrative
        document_context = self._build_context_narrative(vector_results[:15], doc_context)
        
        # Build context string with better organization
        context_parts = [document_context]
        
        # Add graph entities only if highly relevant
        if graph_context and graph_context.get("entities"):
            context_parts.append("\n" + "="*70)
            context_parts.append("RELATED CONCEPTS FROM KNOWLEDGE BASE")
            context_parts.append("="*70)
            for entity in graph_context["entities"][:8]:
                context_parts.append(
                    f"• {entity['name']} ({entity['type']}): {entity.get('description', 'N/A')[:200]}"
                )
        
        # Add relationships
        if graph_context and graph_context.get("relationships"):
            context_parts.append("\n" + "="*70)
            context_parts.append("KEY RELATIONSHIPS")
            context_parts.append("="*70)
            for rel in graph_context["relationships"][:6]:
                context_parts.append(
                    f"→ {rel['source_name']} —[{rel['type']}]→ {rel['target_name']}"
                )
        
        context_str = "\n".join(context_parts)
        
        # Build improved prompt with better instructions
        prompt = f"""You are an expert research assistant analyzing provided documents.

QUERY: {query}

INSTRUCTIONS:
1. Synthesize a comprehensive answer using ALL relevant information from the provided documents
2. Integrate information across multiple documents when relevant
3. Structure your answer logically (not page-by-page, but by topic/theme)
4. Provide specific citations with document names and page numbers
5. If information spans multiple pages, explain the progression and connections
6. Be thorough but well-organized
7. Only use information present in the provided context

PROVIDED CONTEXT:
{context_str}

ANSWER:"""
        
        try:
            response = ollama.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                options={"temperature": 0.2, "top_k": 40, "top_p": 0.9}
            )
            
            answer_text = response['response'].strip()
            
            # Extract structured reasoning
            reasoning = f"Synthesized from {len(vector_results)} text chunks across {len(doc_context)} document(s)"
            if graph_context:
                reasoning += f" and {len(graph_context.get('entities', []))} related concepts"
            
            return {
                "answer": answer_text,
                "reasoning": reasoning
            }
            
        except Exception as e:
            return {
                "answer": f"Error generating answer: {str(e)}",
                "reasoning": "LLM synthesis failed."
            }
    
    def _synthesize_relationship_answer(
        self,
        entity1: str,
        entity2: str,
        paths: List[str]
    ) -> str:
        """Synthesize natural language explanation of relationships."""
        
        prompt = f"""Explain how {entity1} and {entity2} are connected based on these relationship paths:

PATHS:
{chr(10).join([f"{i+1}. {p}" for i, p in enumerate(paths)])}

Provide a clear, concise explanation in 2-3 sentences."""
        
        try:
            response = ollama.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                options={"temperature": 0.3}
            )
            return response['response'].strip()
        except Exception as e:
            return f"{entity1} and {entity2} are connected through {len(paths)} path(s) in the knowledge graph."
    
    def _explain_path(self, path: List[Dict[str, Any]]) -> str:
        """Convert a path into human-readable explanation."""
        explanation_parts = []
        
        for i, item in enumerate(path):
            if i % 2 == 0:  # Entity
                explanation_parts.append(item["name"])
            else:  # Relationship
                explanation_parts.append(f"--[{item['type']}]-->")
        
        return " ".join(explanation_parts)
    
    def _format_citations(self, vector_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format vector results as rich citations with document references."""
        # Group citations by document for cleaner presentation
        citations_by_doc = {}
        
        for result in vector_results:
            metadata = result.get('metadata', {})
            doc_id = result.get('doc_id', 'unknown')
            filename = metadata.get('filename', 'Unknown')
            page = metadata.get('page', 0)
            
            if filename not in citations_by_doc:
                citations_by_doc[filename] = {
                    "doc_id": doc_id,
                    "filename": filename,
                    "pages": [],  # Changed from set() to list
                    "excerpts": []
                }
            
            # Only add page if not already present
            if page not in citations_by_doc[filename]["pages"]:
                citations_by_doc[filename]["pages"].append(page)
            
            # Only include unique high-quality excerpts
            if len(citations_by_doc[filename]["excerpts"]) < 3:
                excerpt = result["text"][:300]
                if excerpt not in [e["text"] for e in citations_by_doc[filename]["excerpts"]]:
                    citations_by_doc[filename]["excerpts"].append({
                        "text": excerpt + "..." if len(result["text"]) > 300 else excerpt,
                        "page": page,
                        "relevance": result.get('relevance_score', 0)
                    })
        
        # Format final citations
        citations = []
        for filename, doc_info in sorted(citations_by_doc.items()):
            page_list = sorted(doc_info["pages"])
            page_str = f"pp. {page_list[0]}-{page_list[-1]}" if len(page_list) > 1 else f"p. {page_list[0]}"
            
            citations.append({
                "source": filename,
                "doc_id": doc_info["doc_id"],
                "pages": page_str,
                "excerpt": doc_info["excerpts"][0]["text"] if doc_info["excerpts"] else "..."
            })
        
        return citations
    
    def _format_relationships(self, graph_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format graph relationships for display."""
        relationships = []
        
        for rel in graph_context["relationships"][:10]:
            relationships.append({
                "source": rel["source_name"],
                "type": rel["type"],
                "target": rel["target_name"],
                "context": rel["context"][:100] if rel["context"] else None
            })
        
        return relationships
