"""Tiny WebSocket fan-out: the listener pushes field snapshots, the Chrome
extension (and the web dashboard, if it wants) subscribe by session.

Client -> server:  {"type": "subscribe", "session_id": "<room>"}
Server -> client:  {"type": "fields", "session_id": "<room>", "fields": {...},
                    "sent_at": <epoch ms>}   # for a browser-side arrival-lag log

Runs in the listener process. One port, no auth (demo; add a token before prod).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import websockets

logger = logging.getLogger("copilot-listener.ws")


class FieldsWS:
    def __init__(self, port: int = 8765):
        self.port = port
        self._subs: dict[str, set] = {}
        self._server = None

    async def start(self) -> None:
        self._server = await websockets.serve(self._handle, "", self.port)
        logger.info("fields WS on :%d", self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, ws) -> None:
        session_id = None
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if msg.get("type") == "subscribe" and msg.get("session_id"):
                    session_id = str(msg["session_id"])
                    self._subs.setdefault(session_id, set()).add(ws)
                    logger.info("subscriber for %s (%d total)", session_id, len(self._subs[session_id]))
        finally:
            if session_id and ws in self._subs.get(session_id, ()):
                self._subs[session_id].discard(ws)

    async def broadcast(self, session_id: str, fields: dict[str, str]) -> None:
        targets = list(self._subs.get(str(session_id), ()))
        if not targets:
            return
        payload = json.dumps({"type": "fields", "session_id": str(session_id),
                              "fields": fields, "sent_at": time.time() * 1000})
        results = await asyncio.gather(
            *(t.send(payload) for t in targets), return_exceptions=True
        )
        for t, r in zip(targets, results):
            if isinstance(r, Exception):
                self._subs[str(session_id)].discard(t)
