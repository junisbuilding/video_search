from __future__ import annotations

from pathlib import Path

import xxhash

SEGMENT_BYTES: int = 1_000_000  # 1 MB per segment


def content_hash(path: Path) -> str:
    """Fast file fingerprint: xxh64 of (first MB || middle MB || last MB || size)."""
    size = path.stat().st_size
    h = xxhash.xxh64()

    with path.open("rb") as f:
        # First segment
        h.update(f.read(min(SEGMENT_BYTES, size)))

        # Middle segment, only if file is large enough to have a distinct middle
        if size > 3 * SEGMENT_BYTES:
            f.seek(size // 2 - SEGMENT_BYTES // 2)
            h.update(f.read(SEGMENT_BYTES))

        # Last segment, only if file is larger than one segment
        if size > SEGMENT_BYTES:
            f.seek(max(0, size - SEGMENT_BYTES))
            h.update(f.read(SEGMENT_BYTES))

    h.update(str(size).encode("ascii"))
    return h.hexdigest()
