"""Shared pytest fixtures."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tiny_video(fixtures_dir: Path) -> Path:
    p = fixtures_dir / "tiny.mp4"
    if not p.exists():
        raise FileNotFoundError(
            "tests/fixtures/tiny.mp4 missing. Regenerate with: "
            "ffmpeg -y -f lavfi -i testsrc=duration=2:size=320x240:rate=10 "
            "-pix_fmt yuv420p tests/fixtures/tiny.mp4"
        )
    return p
