"""Clean up orphaned database entries where files no longer exist."""
import logging
from pathlib import Path
from app.core.database import get_session, Document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_orphaned_files():
    """Remove database entries for files that no longer exist."""
    session = get_session()
    
    try:
        # Get all documents from database
        documents = session.query(Document).all()
        deleted_count = 0
        
        logger.info(f"Checking {len(documents)} documents...")
        
        for doc in documents:
            file_path = Path(doc.file_path)
            if not file_path.exists():
                logger.info(f"Deleting orphaned record: {doc.filename} (file not found at {file_path})")
                session.delete(doc)
                deleted_count += 1
        
        session.commit()
        
        logger.info(f"Cleanup complete: Deleted {deleted_count} orphaned records")
        logger.info(f"Remaining documents: {len(documents) - deleted_count}")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    cleanup_orphaned_files()
