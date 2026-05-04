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


def test_health_includes_watchers_field(client, mock_videos, mock_watcher):
    mock_videos.list_by_status.return_value = []
    mock_watcher.status.return_value = []
    r = client.get("/api/health")
    assert "watchers" in r.json()
    assert isinstance(r.json()["watchers"], list)


def test_health_reports_active_watcher(client, mock_videos, mock_watcher):
    from videosearch.scanning.watcher import WatchStatus
    mock_videos.list_by_status.return_value = []
    mock_watcher.status.return_value = [
        WatchStatus(folder_id="f1", path="/movies", active=True, error=None)
    ]
    r = client.get("/api/health")
    watchers = r.json()["watchers"]
    assert len(watchers) == 1
    assert watchers[0]["folder_id"] == "f1"
    assert watchers[0]["path"] == "/movies"
    assert watchers[0]["active"] is True
    assert watchers[0]["error"] is None


def test_health_reports_inactive_watcher_with_error(client, mock_videos, mock_watcher):
    from videosearch.scanning.watcher import WatchStatus
    mock_videos.list_by_status.return_value = []
    mock_watcher.status.return_value = [
        WatchStatus(folder_id="f1", path="/movies", active=False, error="inotify limit reached")
    ]
    r = client.get("/api/health")
    w = r.json()["watchers"][0]
    assert w["active"] is False
    assert "inotify" in w["error"]
