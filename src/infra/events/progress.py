"""
Sistema de eventos de progreso para operaciones async.
Permite emitir eventos SSE desde cualquier punto del backend.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class ProgressEvent:
    stage: str          # routing | executing | generating | uploading | done | error
    pct: int            # 0-100
    agent: Optional[str] = None
    message: Optional[str] = None
    detail: Optional[str] = None


class ProgressEmitter:
    """
    Emite eventos de progreso a través de un asyncio.Queue.
    El endpoint SSE consume de esta queue.
    """

    def __init__(self):
        self._queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()

    async def emit(self, stage: str, pct: int, agent: str = None, message: str = None, detail: str = None):
        event = ProgressEvent(stage=stage, pct=pct, agent=agent, message=message, detail=detail)
        await self._queue.put(event)

    async def done(self):
        """Señala que no hay más eventos."""
        await self._queue.put(None)

    async def __aiter__(self):
        """Permite iterar async sobre los eventos."""
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event

    def to_sse(self, event: ProgressEvent) -> str:
        """Formatea un evento como SSE."""
        data = json.dumps(asdict(event), ensure_ascii=False)
        return f"event: progress\ndata: {data}\n\n"

    def to_sse_done(self, payload: dict) -> str:
        """Formatea el evento final con la respuesta completa."""
        data = json.dumps(payload, ensure_ascii=False, default=str)
        return f"event: done\ndata: {data}\n\n"

    def to_sse_error(self, error: str) -> str:
        """Formatea un evento de error."""
        data = json.dumps({"error": error}, ensure_ascii=False)
        return f"event: error\ndata: {data}\n\n"