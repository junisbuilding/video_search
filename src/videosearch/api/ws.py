from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect


class JobBroadcaster:
    """Thread-safe broadcaster: sync worker thread → async WebSocket clients."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._clients: set[WebSocket] = set()

    def register(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def send_all(self, event: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_json(event)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    def broadcast(self, event: dict) -> None:
        """Call from any thread to push an event to all connected WS clients."""
        asyncio.run_coroutine_threadsafe(self.send_all(event), self._loop)


def make_ws_router(get_broadcaster_dep, get_jobs_queue_dep) -> APIRouter:
    ws_router = APIRouter()

    @ws_router.websocket("/ws/jobs")
    async def ws_jobs(
        websocket: WebSocket,
        broadcaster: JobBroadcaster = Depends(get_broadcaster_dep),
        jobs_queue=Depends(get_jobs_queue_dep),
    ) -> None:
        await websocket.accept()
        broadcaster.register(websocket)
        try:
            for job in jobs_queue.list_recent(200):
                await websocket.send_json({
                    "job_id": job.id,
                    "video_id": job.video_id,
                    "path": job.path,
                    "kind": job.kind,
                    "status": job.status,
                    "progress": job.progress,
                    "error": job.error,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                })
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.unregister(websocket)

    return ws_router
