"""API key configuration routes for the Atlas Framework."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_env_path, settings

router = APIRouter(prefix="/config")
logger = logging.getLogger(__name__)


class ConfigKeysStatus(BaseModel):
    has_openai: bool
    has_anthropic: bool
    has_deepseek: bool
    has_minimax: bool


class ConfigKeysUpdate(BaseModel):
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    MINIMAX_API_KEY: Optional[str] = None


class ConfigKeysVerifyResponse(BaseModel):
    openai: bool
    anthropic: bool
    deepseek: bool
    minimax: bool


def _read_env_file() -> str:
    env_path = get_env_path()
    if env_path.exists():
        return env_path.read_text(encoding="utf-8")
    return ""


def _write_env_key(content: str, key: str, value: str) -> str:
    """Update or append a key in .env content."""
    # Remove quotes from value for storage
    clean_value = value.strip().strip('"').strip("'")
    pattern = re.compile(rf'^{re.escape(key)}\s*=.*$', re.MULTILINE)
    new_line = f'{key}="{clean_value}"'
    if pattern.search(content):
        return pattern.sub(new_line, content)
    # Append if not found
    if content and not content.endswith("\n"):
        content += "\n"
    return content + new_line + "\n"


@router.get("/keys", response_model=ConfigKeysStatus)
async def get_keys_status() -> ConfigKeysStatus:
    """Check which API keys are configured (without revealing values)."""
    return ConfigKeysStatus(
        has_openai=bool(settings.OPENAI_API_KEY),
        has_anthropic=bool(settings.ANTHROPIC_API_KEY),
        has_deepseek=bool(settings.DEEPSEEK_API_KEY),
        has_minimax=bool(settings.MINIMAX_API_KEY),
    )


@router.post("/keys")
async def update_keys(body: ConfigKeysUpdate) -> Dict[str, str]:
    """Save API keys to config/.env and update runtime settings."""
    env_path = get_env_path()
    try:
        content = _read_env_file()

        updates = body.model_dump(exclude_none=True)
        if not updates:
            return {"status": "ok", "message": "No keys to update"}

        for key, value in updates.items():
            if value is not None:
                content = _write_env_key(content, key, value)
                # Update runtime settings immediately
                setattr(settings, key, value.strip().strip('"').strip("'"))

        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(content, encoding="utf-8")

        return {"status": "ok", "message": f"Updated {len(updates)} key(s)"}
    except Exception as exc:
        logger.error("Failed to save API keys: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save keys: {exc}") from exc


@router.post("/keys/verify", response_model=ConfigKeysVerifyResponse)
async def verify_keys() -> ConfigKeysVerifyResponse:
    """Verify API keys by making lightweight API calls."""
    results = {
        "openai": False,
        "anthropic": False,
        "deepseek": False,
        "minimax": False,
    }

    try:
        import litellm
    except ImportError:
        return ConfigKeysVerifyResponse(**results)

    async def _check(model: str, key_value: str) -> bool:
        if not key_value:
            return False
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False

    if settings.DEEPSEEK_API_KEY:
        results["deepseek"] = await _check("deepseek/deepseek-chat", settings.DEEPSEEK_API_KEY)
    if settings.OPENAI_API_KEY:
        results["openai"] = await _check("openai/gpt-4o-mini", settings.OPENAI_API_KEY)
    if settings.ANTHROPIC_API_KEY:
        results["anthropic"] = await _check("anthropic/claude-haiku-4-5-20251001", settings.ANTHROPIC_API_KEY)
    if settings.MINIMAX_API_KEY:
        results["minimax"] = await _check("minimax/MiniMax-Text-01", settings.MINIMAX_API_KEY)

    return ConfigKeysVerifyResponse(**results)
