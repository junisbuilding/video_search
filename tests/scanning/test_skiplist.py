from pathlib import Path

import pytest

from videosearch.scanning.skiplist import should_skip


@pytest.fixture
def video_file(tmp_path: Path) -> Path:
    p = tmp_path / "movie.mp4"
    p.write_bytes(b"\x00" * 200_000)  # 200 KB
    return p


def test_accepts_valid_video(video_file: Path):
    assert should_skip(video_file) is False


def test_skips_dotfile(tmp_path: Path):
    p = tmp_path / ".hidden.mp4"
    p.write_bytes(b"\x00" * 200_000)
    assert should_skip(p) is True


def test_skips_ds_store(tmp_path: Path):
    p = tmp_path / ".DS_Store"
    p.write_bytes(b"\x00" * 200_000)
    assert should_skip(p) is True


def test_skips_non_video_extension(tmp_path: Path):
    p = tmp_path / "notes.txt"
    p.write_bytes(b"\x00" * 200_000)
    assert should_skip(p) is True


def test_skips_too_small(tmp_path: Path):
    p = tmp_path / "tiny.mp4"
    p.write_bytes(b"\x00" * 1024)  # 1 KB
    assert should_skip(p) is True


def test_skips_inside_photoslibrary_bundle(tmp_path: Path):
    bundle = tmp_path / "MyPhotos.photoslibrary"
    bundle.mkdir()
    p = bundle / "movie.mp4"
    p.write_bytes(b"\x00" * 200_000)
    assert should_skip(p) is True


def test_skips_missing_file(tmp_path: Path):
    p = tmp_path / "ghost.mp4"
    assert should_skip(p) is True
