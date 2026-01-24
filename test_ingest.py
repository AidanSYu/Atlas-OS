#!/usr/bin/env python3
"""
Quick test script to check ingestion and entity extraction.
"""

import sys
sys.path.insert(0, './backend')

from backend.knowledge_graph import KnowledgeGraph
from backend.document_store import DocumentStore

def main():
    kg = KnowledgeGraph()
    ds = DocumentStore()
    
    # List all documents
    documents = ds.list_documents(limit=100)
    print(f"\n{'='*60}")
    print(f"DOCUMENTS: {len(documents)} total")
    print(f"{'='*60}")
    for doc in documents:
        print(f"  {doc['filename']} (ID: {doc['id'][:8]}...) - Status: {doc['status']}")
    
    # List all entities
    entities = kg.find_entities(limit=1000)
    print(f"\n{'='*60}")
    print(f"ENTITIES: {len(entities)} total")
    print(f"{'='*60}")
    
    # Count by type
    by_type = {}
    for entity in entities:
        etype = entity['type']
        by_type[etype] = by_type.get(etype, 0) + 1
    
    for etype, count in sorted(by_type.items()):
        print(f"  {etype}: {count}")
    
    # Show sample entities
    if entities:
        print(f"\nSample entities:")
        for entity in entities[:10]:
            print(f"  - {entity['name']} ({entity['type']}) from doc {entity['document_id'][:8]}...")
    
    # Count relationships
    session = kg.session
    from backend.database import Relationship
    rel_count = session.query(Relationship).count()
    print(f"\n{'='*60}")
    print(f"RELATIONSHIPS: {rel_count} total")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
