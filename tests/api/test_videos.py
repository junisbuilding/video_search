from __future__ import annotations

import time
from unittest.mock import patch

from videosearch.storage.schemas import FrameEmbeddingRow, VideoRow
from videosearch.storage.schemas import SIGLIP_DIM


def _video(id_: str = "v1", status: str = "indexed", path: str | None = None) -> VideoRow:
    return VideoRow(
        id=id_, path=path or f"/videos/{id_}.mp4", hash=id_,
        duration_sec=60.0, fps=30.0, width=1920, height=1080,
        mtime=time.time(), status=status, last_seen_at=time.time(),
    )


def _frame(video_id: str, frame_idx: int, thumb_path: str) -> FrameEmbeddingRow:
    return FrameEmbeddingRow(
        video_id=video_id, frame_idx=frame_idx, timestamp_sec=float(frame_idx),
        embedding=[0.1] * SIGLIP_DIM, thumb_path=thumb_path,
    )


def test_stream_returns_404_for_unknown_video(client, mock_videos):
    mock_videos.find_by_id.return_value = None
    r = client.get("/api/videos/v1/stream")
    assert r.status_code == 404


def test_stream_returns_410_for_missing_video(client, mock_videos):
    mock_videos.find_by_id.return_value = _video(status="missing")
    r = client.get("/api/videos/v1/stream")
    assert r.status_code == 410


def test_stream_returns_404_when_file_not_on_disk(client, mock_videos, tmp_path):
    mock_videos.find_by_id.return_value = _video(path="/nonexistent/file.mp4")
    r = client.get("/api/videos/v1/stream")
    assert r.status_code == 404


def test_stream_returns_file_when_exists(client, mock_videos, tmp_path):
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"fake video content")
    mock_videos.find_by_id.return_value = _video(path=str(video_file))
    r = client.get("/api/videos/v1/stream")
    assert r.status_code == 200
    assert b"fake video content" in r.content


def test_thumb_returns_404_for_unknown_frame(client, mock_frames):
    mock_frames.find_frame.return_value = None
    r = client.get("/api/videos/v1/thumbs/1")
    assert r.status_code == 404


def test_thumb_returns_404_when_file_not_on_disk(client, mock_frames):
    row = FrameEmbeddingRow(
        video_id="v1", frame_idx=1, timestamp_sec=1.0,
        embedding=[0.1] * SIGLIP_DIM, thumb_path="/nonexistent/frame.jpg",
    )
    mock_frames.find_frame.return_value = row
    r = client.get("/api/videos/v1/thumbs/1")
    assert r.status_code == 404


def test_thumb_serves_jpeg_file(client, mock_frames, tmp_path):
    thumb = tmp_path / "frame.jpg"
    thumb.write_bytes(b"fake jpeg")
    mock_frames.find_frame.return_value = _frame("v1", 1, str(thumb))
    r = client.get("/api/videos/v1/thumbs/1")
    assert r.status_code == 200
    assert b"fake jpeg" in r.content


def test_reveal_returns_404_for_unknown_video(client, mock_videos):
    mock_videos.find_by_id.return_value = None
    r = client.post("/api/videos/v1/reveal")
    assert r.status_code == 404


def test_reveal_returns_404_when_file_not_on_disk(client, mock_videos):
    mock_videos.find_by_id.return_value = _video(path="/nonexistent/file.mp4")
    r = client.post("/api/videos/v1/reveal")
    assert r.status_code == 404


def test_reveal_calls_open_on_macos(client, mock_videos, tmp_path):
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"x")
    mock_videos.find_by_id.return_value = _video(path=str(video_file))
    with patch("sys.platform", "darwin"), patch("subprocess.Popen") as mock_popen:
        r = client.post("/api/videos/v1/reveal")
    assert r.status_code == 200
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert args == ["open", "-R", str(video_file)]


def test_reveal_returns_501_on_linux_without_display(client, mock_videos, tmp_path, monkeypatch):
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"x")
    mock_videos.find_by_id.return_value = _video(path=str(video_file))
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with patch("sys.platform", "linux"):
        r = client.post("/api/videos/v1/reveal")
    assert r.status_code == 501
