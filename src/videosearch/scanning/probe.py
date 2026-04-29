from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ProbeError(RuntimeError):
    """ffprobe failed or output was unrecognizable."""


@dataclass(frozen=True)
class VideoInfo:
    duration_sec: float
    fps: float
    width: int
    height: int


def probe(path: Path) -> VideoInfo:
    """Run ffprobe and return the first video stream's metadata."""
    if not path.exists():
        raise ProbeError(f"file not found: {path}")

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-print_format", "json",
                "-show_streams", "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ProbeError(f"ffprobe failed: {e.stderr.strip()}") from e

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ProbeError(f"ffprobe returned non-JSON output: {e}") from e

    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        raise ProbeError(f"no video stream found in {path}")
    video = video_streams[0]

    duration = data.get("format", {}).get("duration")
    if duration is None:
        duration = video.get("duration", 0)
    duration_sec = float(duration)

    fps = _parse_rate(video.get("avg_frame_rate", "0/0"))
    if fps == 0:
        fps = _parse_rate(video.get("r_frame_rate", "0/0"))

    return VideoInfo(
        duration_sec=duration_sec,
        fps=fps,
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
    )


def _parse_rate(rate: str) -> float:
    """Convert ffprobe-style 'num/den' to a float (0.0 if invalid)."""
    try:
        num_s, _, den_s = rate.partition("/")
        num, den = int(num_s), int(den_s)
        return num / den if den > 0 else 0.0
    except ValueError:
        return 0.0
