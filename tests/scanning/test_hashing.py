from pathlib import Path

from videosearch.scanning.hashing import content_hash


def _write_bytes(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_hash_is_stable(tmp_path: Path):
    p = _write_bytes(tmp_path / "a.mp4", b"hello world" * 1000)
    assert content_hash(p) == content_hash(p)


def test_hash_differs_for_different_content(tmp_path: Path):
    a = _write_bytes(tmp_path / "a.mp4", b"\x00" * 5_000_000)
    b = _write_bytes(tmp_path / "b.mp4", b"\x01" * 5_000_000)
    assert content_hash(a) != content_hash(b)


def test_hash_handles_small_file(tmp_path: Path):
    """Files smaller than the segment-window thresholds still hash deterministically."""
    p = _write_bytes(tmp_path / "small.mp4", b"abcdef" * 100)  # 600 bytes
    h1 = content_hash(p)
    h2 = content_hash(p)
    assert h1 == h2
    assert len(h1) == 16  # xxh64 hex


def test_hash_differs_when_size_differs(tmp_path: Path):
    a = _write_bytes(tmp_path / "a.mp4", b"\x42" * 1_000_000)
    b = _write_bytes(tmp_path / "b.mp4", b"\x42" * 2_000_000)
    assert content_hash(a) != content_hash(b)
