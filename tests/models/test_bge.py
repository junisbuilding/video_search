from unittest.mock import MagicMock, patch

import numpy as np

from videosearch.models.bge import BgeTextEmbedder
from videosearch.storage.schemas import TEXT_EMBED_DIM


def _make_embedder(n: int = 2) -> tuple[BgeTextEmbedder, MagicMock]:
    mock_st = MagicMock()
    mock_st.encode.return_value = np.random.randn(n, TEXT_EMBED_DIM).astype("float32")
    with patch("videosearch.models.bge.SentenceTransformer") as MockST:
        MockST.return_value = mock_st
        embedder = BgeTextEmbedder("mock-model")
    return embedder, mock_st


def test_embed_text_batch_shape():
    embedder, mock_st = _make_embedder(n=3)
    mock_st.encode.return_value = np.random.randn(3, TEXT_EMBED_DIM).astype("float32")

    result = embedder.embed_text(["hello", "world", "foo"])

    assert len(result) == 3
    assert len(result[0]) == TEXT_EMBED_DIM


def test_embed_text_single_shape():
    embedder, mock_st = _make_embedder(n=1)
    mock_st.encode.return_value = np.random.randn(1, TEXT_EMBED_DIM).astype("float32")

    result = embedder.embed_text(["hello"])

    assert len(result) == 1
    assert len(result[0]) == TEXT_EMBED_DIM


def test_embed_text_calls_encode_with_normalize():
    embedder, mock_st = _make_embedder(n=1)

    embedder.embed_text(["test"])

    mock_st.encode.assert_called_once()
    _, kwargs = mock_st.encode.call_args
    assert kwargs.get("normalize_embeddings") is True
