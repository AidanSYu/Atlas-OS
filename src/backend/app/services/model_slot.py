"""Single GPU-resident LLM slot.

Atlas loads large GGUFs (ingestion LLM, Nemotron orchestrator) into the same
VRAM. They can't coexist on a 4GB card. This module coordinates eviction: a
service calls :func:`acquire` before constructing its ``Llama`` instance, which
fires the previous owner's unload callback so there is never more than one
resident model.

One-way eviction is fine in both directions — whichever service is about to
load the GPU takes the slot.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class _ModelSlot:
    def __init__(self) -> None:
        self._owner: Optional[str] = None
        self._unload_cb: Optional[Callable[[], None]] = None
        self._lock = threading.Lock()

    def acquire(self, owner: str, unload_cb: Callable[[], None]) -> None:
        """Claim the slot for ``owner``. Evicts the prior owner if any.

        ``unload_cb`` must be safe to call from any thread and idempotent.
        """
        with self._lock:
            prior_owner = self._owner
            prior_cb = self._unload_cb
            self._owner = owner
            self._unload_cb = unload_cb

        if prior_owner and prior_owner != owner and prior_cb is not None:
            logger.info("Model slot: evicting '%s' for '%s'", prior_owner, owner)
            try:
                prior_cb()
            except Exception as exc:
                logger.warning("Unload callback for '%s' raised: %s", prior_owner, exc)

    def release(self, owner: str) -> None:
        """Clear the slot if ``owner`` still holds it."""
        with self._lock:
            if self._owner == owner:
                self._owner = None
                self._unload_cb = None

    @property
    def owner(self) -> Optional[str]:
        return self._owner


_slot = _ModelSlot()


def acquire(owner: str, unload_cb: Callable[[], None]) -> None:
    _slot.acquire(owner, unload_cb)


def release(owner: str) -> None:
    _slot.release(owner)


def current_owner() -> Optional[str]:
    return _slot.owner
