from __future__ import annotations

import time
from videosearch.storage.schemas import VideoRow


def test_health_returns_ok(client, mock_videos):
    mock_videos.list_by_status.return_value = []
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded")
    assert isinstance(data["db"], bool)
    assert isinstance(data["models_loaded"], bool)
    assert data["gpu_backend"] in ("mps", "cuda", "cpu")
    assert isinstance(data["indexed_count"], int)


def test_health_reports_indexed_count(client, mock_videos):
    videos = [
        VideoRow(id=f"v{i}", path=f"/v{i}.mp4", hash=f"h{i}",
                 duration_sec=10.0, fps=30.0, width=1920, height=1080,
                 mtime=time.time(), status="indexed", last_seen_at=time.time())
        for i in range(3)
    ]
    mock_videos.list_by_status.return_value = videos
    r = client.get("/api/health")
    assert r.json()["indexed_count"] == 3


def test_health_degraded_when_db_fails(client, mock_videos):
    mock_videos.list_by_status.side_effect = RuntimeError("db down")
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"
    assert r.json()["db"] is False
