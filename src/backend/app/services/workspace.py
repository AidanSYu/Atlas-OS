"""
Atlas 3.0: Workspace Service
Handles persistent storage of user and agent drafts in the data/drafts/ directory.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

from app.core.config import settings

logger = logging.getLogger(__name__)

class WorkspaceService:
    def __init__(self):
        self.drafts_dir = Path(settings.DRAFTS_DIR)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"WorkspaceService initialized with drafts dir: {self.drafts_dir}")

    def _get_project_dir(self, project_id: str) -> Path:
        """Get the directory for a specific project, creating it if necessary."""
        project_dir = self.drafts_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    def list_drafts(self, project_id: str) -> List[Dict[str, Any]]:
        """List all drafts in a project's workspace."""
        project_dir = self._get_project_dir(project_id)
        drafts = []
        for file_path in project_dir.glob("*.json"):
            try:
                stat = file_path.stat()
                drafts.append({
                    "id": file_path.stem,
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "updated_at": stat.st_mtime,
                })
            except Exception as e:
                logger.warning(f"Error reading draft metadata for {file_path}: {e}")
        
        # Sort by updated_at descending
        return sorted(drafts, key=lambda x: x["updated_at"], reverse=True)

    def get_draft(self, project_id: str, draft_id: str) -> Optional[Dict[str, Any]]:
        """Read a draft from the workspace."""
        file_path = self._get_project_dir(project_id) / f"{draft_id}.json"
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            
            return {
                "id": draft_id,
                "filename": file_path.name,
                "content": content,
                "updated_at": file_path.stat().st_mtime
            }
        except Exception as e:
            logger.error(f"Error reading draft {file_path}: {e}")
            raise ValueError(f"Failed to read draft: {e}")

    def save_draft(self, project_id: str, draft_id: str, content: Any) -> Dict[str, Any]:
        """Save a draft to the workspace."""
        file_path = self._get_project_dir(project_id) / f"{draft_id}.json"
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            
            return {
                "id": draft_id,
                "filename": file_path.name,
                "status": "saved",
                "updated_at": file_path.stat().st_mtime
            }
        except Exception as e:
            logger.error(f"Error saving draft {file_path}: {e}")
            raise ValueError(f"Failed to save draft: {e}")

    def delete_draft(self, project_id: str, draft_id: str) -> bool:
        """Delete a draft from the workspace."""
        file_path = self._get_project_dir(project_id) / f"{draft_id}.json"
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception as e:
                logger.error(f"Error deleting draft {file_path}: {e}")
                return False
        return False
