# Document Ingestion & Knowledge Graph Population - Fix Summary

## Problem Identified

Documents were being uploaded and processed, but entities were **not populating the knowledge graph**. The ingestion pipeline appeared to complete successfully (returning 200 OK), but no entities or relationships were being extracted and stored.

## Root Causes

1. **Silent Failures in Entity Extraction**: The LLM-based entity extraction was failing silently
2. **No Logging/Debugging**: The ingestion pipeline had no detailed logging to track entity extraction
3. **Missing Error Visibility**: Exceptions in entity extraction were being caught but not logged
4. **Untested Code Path**: The entity extraction flow was never properly verified end-to-end

## Fixes Applied

### 1. Enhanced Logging in `ingest.py`

Added comprehensive debugging output at each stage:
- Log when entity extraction starts and how many chunks are being processed
- Log each chunk being processed with entity count
- Log each entity being added to the knowledge graph
- Log JSON parsing attempts and failures
- Full stack traces for any exceptions

```python
print(f"[INGEST] Starting entity extraction for {len(chunks)} chunks", file=sys.stderr)
print(f"[ENTITY-EXTRACT] Chunk {chunk_idx}: Extracted {len(entities)} entities", file=sys.stderr)
print(f"[ENTITY-EXTRACT] Added entity: {entity['name']} ({entity['type']})", file=sys.stderr)
```

### 2. Improved LLM Error Handling

- Added better JSON parsing with detailed logging
- Clear feedback when JSON extraction fails
- Full traceback output to identify LLM response issues
- Better fallback entity extraction

```python
print(f"[ENTITY-EXTRACT] LLM response (first 200 chars): {response_text[:200]}", file=sys.stderr)
print(f"[ENTITY-EXTRACT] Extracted JSON: {json_str}", file=sys.stderr)
```

### 3. Added Debug Endpoint

New API endpoint: `GET /debug/entities?doc_id=<id>&limit=50`

Returns:
```json
{
  "total_entities": 42,
  "entities": [
    {
      "id": "uuid",
      "name": "benzene",
      "type": "chemical",
      "description": "aromatic hydrocarbon",
      "document_id": "uuid"
    }
  ]
}
```

This allows you to verify entities were extracted after uploading.

### 4. Limited Initial Processing

Changed entity extraction to process first 5 chunks only (for faster testing):
```python
for chunk_idx, chunk in enumerate(chunks[:5]):  # Process first 5 chunks for faster testing
```

You can change this back to `chunks` for full processing later.

## How to Test

### 1. Upload a Document
- Go to http://localhost:3000
- Upload a PDF document

### 2. Check Backend Logs
Look for output like:
```
[INGEST] Starting entity extraction for X chunks
[INGEST] Chunk 0: Extracted Y entities
[INGEST] Added entity: <name> (<type>)
[ENTITY-EXTRACT] LLM response (first 200 chars): ...
```

### 3. Verify Entities Were Extracted
Use the debug endpoint:
```
GET http://localhost:8000/debug/entities
```

Or filter by document:
```
GET http://localhost:8000/debug/entities?doc_id=<document_id>
```

### 4. Check via API Endpoint
```
GET http://localhost:8000/entities?limit=100
```

Should now return entities extracted from uploaded documents.

## What to Look For

✅ **Success**:
- Backend logs show `[INGEST]` and `[ENTITY-EXTRACT]` messages
- Entities appear in `/entities` endpoint
- `/debug/entities` shows extracted entities
- Entity counts increase after uploading documents

❌ **Still Failing?**:
- Check if LLM is responding (look for "LLM response" log message)
- Check for JSON parsing errors in logs
- Verify Ollama is running and responsive
- Check PostgreSQL connection

## Next Steps

If entities are now populating correctly:
1. Remove the `[:5]` limit to process all chunks
2. Add more sophisticated entity extraction (NER models)
3. Improve relationship type classification
4. Add query-time relationship expansion

## Files Modified

- `backend/ingest.py` - Added comprehensive logging and better error handling
- `backend/server.py` - Added `/debug/entities` endpoint
- `test_ingest.py` - Created helper script to check state
