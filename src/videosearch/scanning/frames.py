from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


class FrameSamplingError(RuntimeError):
    """ffmpeg failed during frame extraction."""


@dataclass(frozen=True)
class FrameSample:
    frame_idx: int
    timestamp_sec: float
    path: Path


def sample_frames(
    video_path: Path,
    *,
    fps: float,
    output_dir: Path,
    jpeg_quality: int = 5,
) -> Iterator[FrameSample]:
    """Sample frames at uniform `fps`, write JPEGs into `output_dir`, yield samples."""
    if fps <= 0:
        raise ValueError("fps must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame-%06d.jpg"
    try:
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(video_path),
                "-vf", f"fps={fps}",
                "-q:v", str(jpeg_quality),
                str(pattern),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise FrameSamplingError(f"ffmpeg failed: {e.stderr.strip()}") from e

    for jpg in sorted(output_dir.glob("frame-*.jpg")):
        # ffmpeg numbers from 1
        idx = int(jpg.stem.split("-")[1])
        timestamp = (idx - 1) / fps
        yield FrameSample(frame_idx=idx, timestamp_sec=timestamp, path=jpg)
