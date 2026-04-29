from pathlib import Path

import pytest

from videosearch.scanning.probe import VideoInfo, ProbeError, probe


def test_probe_returns_metadata(tiny_video: Path):
    info = probe(tiny_video)
    assert isinstance(info, VideoInfo)
    assert info.width == 320
    assert info.height == 240
    assert 1.5 < info.duration_sec < 2.5
    assert info.fps > 0


def test_probe_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(ProbeError):
        probe(tmp_path / "does-not-exist.mp4")


def test_probe_raises_on_nonvideo_file(tmp_path: Path):
    p = tmp_path / "junk.mp4"
    p.write_bytes(b"this is not a real video file")
    with pytest.raises(ProbeError):
        probe(p)
