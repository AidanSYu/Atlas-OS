"""
Shared Qdrant client singleton (embedded, in-process).

All services that need Qdrant should use `get_qdrant_client()` to avoid
multiple locks on the same storage directory.
"""
import logging
import shutil
from pathlib import Path

from qdrant_client import QdrantClient
from app.core.config import settings

logger = logging.getLogger(__name__)

_qdrant_client: QdrantClient | None = None


def _clear_stale_lock(storage_path: str) -> None:
    """Remove stale .lock file left by a previous unclean shutdown."""
    lock_file = Path(storage_path) / ".lock"
    if lock_file.exists():
        try:
            lock_file.unlink()
            logger.info(f"Removed stale Qdrant lock file: {lock_file}")
        except OSError as e:
            logger.warning(f"Could not remove lock file {lock_file}: {e}")


def get_qdrant_client() -> QdrantClient:
    """Return the shared embedded Qdrant client, creating it on first call."""
    global _qdrant_client
    if _qdrant_client is None:
        storage_path = settings.QDRANT_STORAGE_PATH
        try:
            _qdrant_client = QdrantClient(path=storage_path)
        except RuntimeError as e:
            if "already accessed" in str(e):
                logger.warning("Qdrant storage locked — clearing stale lock and retrying")
                _clear_stale_lock(storage_path)
                _qdrant_client = QdrantClient(path=storage_path)
            else:
                raise
        logger.info(f"Shared Qdrant client initialised ({storage_path})")
    return _qdrant_client
