from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

DEFAULT_SKIP_NAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db"})
DEFAULT_BUNDLE_SUFFIXES: tuple[str, ...] = (
    ".photoslibrary",
    ".app",
    ".framework",
    ".bundle",
)
DEFAULT_VIDEO_EXTS: frozenset[str] = frozenset({
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v",
    ".wmv", ".mpg", ".mpeg", ".3gp", ".flv", ".ts",
})
DEFAULT_MIN_SIZE: int = 100_000  # 100 KB


def should_skip(
    path: Path,
    *,
    skip_names: Iterable[str] = DEFAULT_SKIP_NAMES,
    bundle_suffixes: tuple[str, ...] = DEFAULT_BUNDLE_SUFFIXES,
    video_exts: Iterable[str] = DEFAULT_VIDEO_EXTS,
    min_size: int = DEFAULT_MIN_SIZE,
) -> bool:
    """Return True if this path should not be indexed."""
    skip_names_set = set(skip_names)
    video_exts_set = {ext.lower() for ext in video_exts}

    # Bundle ancestor check
    for part in path.parts:
        if part.endswith(bundle_suffixes):
            return True

    # Exact-name skip
    if path.name in skip_names_set:
        return True

    # Hidden / dotfile
    if path.name.startswith("."):
        return True

    # Extension
    if path.suffix.lower() not in video_exts_set:
        return True

    # Size (also catches missing files)
    try:
        if path.stat().st_size < min_size:
            return True
    except FileNotFoundError:
        return True

    return False
