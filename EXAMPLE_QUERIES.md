# Atlas 2.0 - Example Queries

This document demonstrates the different types of queries supported by Atlas 2.0 and their expected outputs.

---

## Setup

Start the system:
```bash
cd backend && python server.py
```

Upload some example documents:
```bash
curl -X POST "http://localhost:8000/ingest" -F "file=@paper1.pdf"
curl -X POST "http://localhost:8000/ingest" -F "file=@paper2.pdf"
```

---

## Query Type 1: Factual Document Questions

**Purpose**: Answer specific questions about document content

### Example Query
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What experimental methods are described in the documents?"
  }'
```

### Expected Response Structure
```json
{
  "answer": "The documents describe several experimental methods including...",
  "reasoning": "Based on 5 relevant chunks from 2 documents...",
  "citations": [
    {
      "text": "We employed a photocatalytic reactor...",
      "source": "paper1.pdf",
      "page": 3,
      "relevance": 0.87
    }
  ],
  "relationships": [],
  "context_sources": {
    "vector_chunks": 5,
    "graph_entities": 8,
    "graph_relationships": 12,
    "documents": 2
  }
}
```

### What Happens Behind the Scenes
1. Query embedded with nomic-embed-text
2. Top-5 semantic search in Qdrant
3. Extract entities from results
4. Expand context via knowledge graph
5. Synthesize answer with llama3.2:1b
6. Return with citations and reasoning

---

## Query Type 2: Relationship Questions

**Purpose**: Discover how entities are connected in the knowledge graph

### Example Query
```bash
curl "http://localhost:8000/query/relationship?entity1=catalyst&entity2=benzene"
```

### Expected Response
```json
{
  "answer": "Catalyst and benzene are connected through a co-occurrence relationship in document 'paper1.pdf'. They appear together in a discussion of hydrogenation reactions where the catalyst facilitates the conversion of benzene to cyclohexane.",
  "paths": [
    "catalyst --[co-occurs]--> Reaction --[produces]--> benzene",
    "catalyst --[uses]--> benzene"
  ],
  "reasoning": "Found 2 connection path(s) in the knowledge graph."
}
```

### What Happens
1. Search for entities matching "catalyst" and "benzene"
2. BFS graph traversal to find paths (max 3 hops)
3. Format paths as human-readable explanations
4. LLM synthesizes natural language explanation

---

## Query Type 3: Document-Specific Questions

**Purpose**: Query a specific document by ID

### Example Query
```bash
# First get document ID
DOC_ID=$(curl -s "http://localhost:8000/files" | jq -r '.[0].doc_id')

# Then query that document
curl "http://localhost:8000/query/document/${DOC_ID}?question=What+are+the+main+findings"
```

### Expected Response
```json
{
  "answer": "The main findings include: 1) The novel catalyst showed 95% selectivity...",
  "document": "paper1.pdf",
  "citations": [
    {
      "text": "Results demonstrate that the synthesized catalyst...",
      "source": "paper1.pdf",
      "page": 7,
      "relevance": 0.92
    }
  ],
  "entities_mentioned": ["catalyst", "selectivity", "yield", "reaction"],
  "reasoning": "Searched 5 relevant chunks from paper1.pdf"
}
```

### What Happens
1. Filter vector search to specific document
2. Get entities from that document
3. Synthesize answer using document-specific context

---

## Query Type 4: Multi-Document Search

**Purpose**: Find all documents mentioning a concept

### Example Query
```bash
curl "http://localhost:8000/query/search?concept=photocatalysis"
```

### Expected Response
```json
{
  "answer": "Found 3 documents mentioning 'photocatalysis'",
  "documents": [
    {
      "filename": "paper1.pdf",
      "doc_id": "abc-123",
      "mentions": 8,
      "relevance": 4.2
    },
    {
      "filename": "paper3.pdf",
      "doc_id": "def-456",
      "mentions": 3,
      "relevance": 2.1
    }
  ],
  "reasoning": "Semantic search found 11 relevant chunks across documents."
}
```

### What Happens
1. Semantic search across all documents
2. Group results by document
3. Calculate relevance scores
4. Return ranked list

---

## Query Type 5: Exploratory Questions

**Purpose**: Open-ended questions that require reasoning

### Example Query
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What factors affect catalyst selectivity based on the research?"
  }'
```

### Expected Response
```json
{
  "answer": "Based on the research, several factors affect catalyst selectivity: 1) Temperature - higher temperatures reduce selectivity (paper1.pdf, p5)...",
  "reasoning": "Synthesized from 5 text chunks and 12 entities including Temperature, Pressure, pH, Catalyst, and Selectivity",
  "citations": [
    {
      "text": "We observed that increasing temperature from 80°C to 120°C...",
      "source": "paper1.pdf",
      "page": 5,
      "relevance": 0.91
    }
  ],
  "relationships": [
    {
      "source": "Temperature",
      "type": "co-occurs",
      "target": "Selectivity",
      "context": "temperature from 80°C to 120°C decreased selectivity from 95% to 78%"
    }
  ],
  "context_sources": {
    "vector_chunks": 5,
    "graph_entities": 12,
    "graph_relationships": 8,
    "documents": 2
  }
}
```

### What Happens
1. Semantic retrieval of relevant chunks
2. Entity extraction from query and results
3. Graph expansion around mentioned entities
4. Multi-document reasoning
5. LLM synthesis with full context

---

## Administrative Queries

### List All Documents
```bash
curl "http://localhost:8000/files"
```

### Get Document by ID
```bash
curl "http://localhost:8000/files/{doc_id}"
```

### Delete Document
```bash
curl -X DELETE "http://localhost:8000/files/{doc_id}"
```

### List Entities
```bash
curl "http://localhost:8000/entities?entity_type=chemical&limit=50"
```

### Get Entity Relationships
```bash
curl "http://localhost:8000/entities/{entity_id}/relationships?direction=both"
```

### System Statistics
```bash
curl "http://localhost:8000/stats"
```

Expected:
```json
{
  "vector_store": {
    "total_vectors": 1234,
    "vector_dimension": 768,
    "distance_metric": "COSINE"
  },
  "document_store": {
    "total_documents": 5,
    "total_chunks": 1234,
    "status_breakdown": {
      "pending": 0,
      "processing": 1,
      "completed": 4,
      "failed": 0
    }
  },
  "entity_types": [
    {"type": "chemical", "count": 45},
    {"type": "experiment", "count": 23},
    {"type": "concept", "count": 67}
  ]
}
```

---

## Advanced Patterns

### Chaining Queries

Find related concepts, then search for them:
```bash
# 1. Find relationship
curl "http://localhost:8000/query/relationship?entity1=catalyst&entity2=reaction"

# 2. Use discovered entities to search
curl "http://localhost:8000/query/search?concept=hydrogenation"
```

### Comparative Analysis
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare the methods used in different papers for catalyst synthesis"
  }'
```

### Temporal Queries
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What improvements were made over time in the reaction conditions?"
  }'
```

---

## Understanding the Response

Every query response includes:

1. **answer** - The synthesized natural language answer
2. **reasoning** - Explanation of how the answer was derived
3. **citations** - Source documents and pages (with snippets)
4. **relationships** - Relevant entity connections from graph
5. **context_sources** - Statistics showing what knowledge was used

This transparency allows you to:
- Trust the answer (it's grounded in documents)
- Verify the reasoning
- Explore the knowledge graph
- Understand system limitations

---

## Performance Expectations

- **First query**: 3-10 seconds (model loading)
- **Subsequent queries**: 1-3 seconds
- **Ingestion**: 5-15 seconds per PDF (depends on size)
- **Entity extraction**: 0.5-2 seconds per chunk

---

## Tips for Better Queries

1. **Be specific**: "What catalyst was used?" vs "Tell me about catalysts"
2. **Use document terms**: If papers use "photocatalyst", use that term
3. **Ask about relationships**: "How are X and Y related?"
4. **Reference entities**: Use capitalized proper nouns
5. **Check entities first**: Use `/entities` to see what's in the graph

---

## Debugging Queries

If results are poor:

1. **Check documents are indexed**:
   ```bash
   curl "http://localhost:8000/files"
   ```

2. **Check entities were extracted**:
   ```bash
   curl "http://localhost:8000/entities?limit=10"
   ```

3. **Check system stats**:
   ```bash
   curl "http://localhost:8000/stats"
   ```

4. **View system health**:
   ```bash
   curl "http://localhost:8000/health"
   ```

---

## Next Steps

- Upload your own documents
- Try the example queries
- Explore the knowledge graph via `/entities`
- Check reasoning transparency in responses
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system details
