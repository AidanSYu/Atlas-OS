"""Clean up orphaned database entries where files no longer exist."""
from pathlib import Path
from app.core.database import get_session, Document

session = get_session()

# Get all documents from database
documents = session.query(Document).all()
deleted_count = 0

print(f"Checking {len(documents)} documents...")

for doc in documents:
    file_path = Path(doc.file_path)
    if not file_path.exists():
        print(f"Deleting orphaned record: {doc.filename} (file not found at {file_path})")
        session.delete(doc)
        deleted_count += 1

session.commit()
session.close()

print(f"\n✅ Cleanup complete: Deleted {deleted_count} orphaned records")
print(f"Remaining documents: {len(documents) - deleted_count}")
