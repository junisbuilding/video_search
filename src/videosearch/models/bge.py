from __future__ import annotations

from collections.abc import Sequence

from sentence_transformers import SentenceTransformer

from videosearch.models._device import select_device


class BgeTextEmbedder:
    def __init__(self, model_name: str, *, device: str | None = None):
        self.device = select_device(device)
        self._model = SentenceTransformer(model_name, device=self.device)

    def embed_text(self, texts: Sequence[str]) -> list[list[float]]:
        vecs = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vecs.tolist()
