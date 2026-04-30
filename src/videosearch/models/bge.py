from __future__ import annotations

from collections.abc import Sequence

import torch
from sentence_transformers import SentenceTransformer


def _select_device(device: str | None) -> str:
    if device is not None:
        return device
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class BgeTextEmbedder:
    def __init__(self, model_name: str, *, device: str | None = None):
        self._model = SentenceTransformer(model_name, device=_select_device(device))

    def embed_text(self, texts: Sequence[str]) -> list[list[float]]:
        vecs = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vecs.tolist()
