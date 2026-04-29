from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from videosearch.storage.schemas import SIGLIP_DIM, TEXT_EMBED_DIM


def _deterministic_vector(seed: bytes, dim: int) -> list[float]:
    """Generate a stable [-1, 1] vector from arbitrary bytes."""
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        h = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for i in range(0, len(h), 2):
            if len(out) >= dim:
                break
            n = int.from_bytes(h[i : i + 2], "big")
            out.append((n / 65535.0) * 2.0 - 1.0)
        counter += 1
    return out[:dim]


class StubImageEmbedder:
    """Hashes the image bytes (or the text) into a SIGLIP_DIM vector."""

    def embed_images(self, images: Sequence[Path]) -> list[list[float]]:
        vectors = []
        for img in images:
            data = img.read_bytes()
            vectors.append(_deterministic_vector(data, SIGLIP_DIM))
        return vectors

    def embed_text(self, text: str) -> list[float]:
        return _deterministic_vector(text.encode("utf-8"), SIGLIP_DIM)


class StubTextEmbedder:
    def embed_text(self, texts: Sequence[str]) -> list[list[float]]:
        return [_deterministic_vector(t.encode("utf-8"), TEXT_EMBED_DIM) for t in texts]


class StubCaptioner:
    """Deterministic caption derived from the input image filenames."""

    def caption(self, images: Sequence[Path], *, prompt: str) -> str:
        names = ", ".join(p.name for p in images)
        return f"stub caption for {names}"
