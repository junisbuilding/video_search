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


@dataclass(frozen=True)
class Scene:
    scene_idx: int
    start_sec: float
    end_sec: float


def detect_scenes(
    video_path: Path,
    *,
    threshold: float = 27.0,
    fallback_duration_sec: float | None = None,
) -> list[Scene]:
    """Detect shot boundaries with PySceneDetect's content detector.

    When the detector finds no cuts (common for short / static videos):
      - if `fallback_duration_sec` is given, return a single scene spanning [0, duration);
      - otherwise return [].
    """
    from scenedetect import ContentDetector, detect

    raw = detect(str(video_path), ContentDetector(threshold=threshold))
    if raw:
        return [
            Scene(
                scene_idx=i,
                start_sec=start.get_seconds(),
                end_sec=end.get_seconds(),
            )
            for i, (start, end) in enumerate(raw)
        ]
    if fallback_duration_sec is not None and fallback_duration_sec > 0:
        return [Scene(scene_idx=0, start_sec=0.0, end_sec=fallback_duration_sec)]
    return []
