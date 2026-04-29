from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class ImageEmbedder(Protocol):
    """Image-text contrastive model (SigLIP family). Provides paired encoders."""

    def embed_images(self, images: Sequence[Path]) -> list[list[float]]: ...
    def embed_text(self, text: str) -> list[float]: ...


class TextEmbedder(Protocol):
    """Pure text retrieval embedder (e.g. bge-small)."""

    def embed_text(self, texts: Sequence[str]) -> list[list[float]]: ...


class Captioner(Protocol):
    """Generates a natural-language caption for one or more images."""

    def caption(self, images: Sequence[Path], *, prompt: str) -> str: ...
