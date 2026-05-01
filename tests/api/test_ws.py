from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from videosearch.api.ws import JobBroadcaster


@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def broadcaster(loop):
    return JobBroadcaster(loop)


def test_register_adds_client(broadcaster):
    ws = MagicMock()
    broadcaster.register(ws)
    assert ws in broadcaster._clients


def test_unregister_removes_client(broadcaster):
    ws = MagicMock()
    broadcaster.register(ws)
    broadcaster.unregister(ws)
    assert ws not in broadcaster._clients


def test_broadcast_calls_run_coroutine_threadsafe(broadcaster):
    event = {"job_id": "j1", "status": "completed"}
    with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
        broadcaster.broadcast(event)
        mock_rct.assert_called_once()
        assert mock_rct.call_args[0][1] is broadcaster._loop


@pytest.mark.anyio
async def test_send_all_delivers_to_registered_clients(loop):
    broadcaster = JobBroadcaster(loop)
    ws = MagicMock()
    ws.send_json = AsyncMock()
    broadcaster.register(ws)
    await broadcaster.send_all({"status": "ok"})
    ws.send_json.assert_awaited_once_with({"status": "ok"})


@pytest.mark.anyio
async def test_send_all_removes_dead_clients(loop):
    broadcaster = JobBroadcaster(loop)
    ws = MagicMock()
    ws.send_json = AsyncMock(side_effect=RuntimeError("disconnected"))
    broadcaster.register(ws)
    await broadcaster.send_all({"status": "ok"})
    assert ws not in broadcaster._clients
