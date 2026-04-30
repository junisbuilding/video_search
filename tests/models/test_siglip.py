from pathlib import Path
from unittest.mock import MagicMock, patch

import torch
from PIL import Image

from videosearch.models.siglip import SiglipEmbedder
from videosearch.storage.schemas import SIGLIP_DIM


def _mock_inputs() -> MagicMock:
    # spec=dict would block .to() since dict has no .to attribute
    m = MagicMock()
    m.keys.return_value = []  # ** unpacking yields empty dict
    m.to.return_value = m
    return m


def _make_embedder() -> tuple[SiglipEmbedder, MagicMock, MagicMock]:
    mock_processor = MagicMock()
    mock_processor.return_value = _mock_inputs()

    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = mock_model
    mock_model.get_image_features.return_value = torch.randn(2, SIGLIP_DIM)
    mock_model.get_text_features.return_value = torch.randn(1, SIGLIP_DIM)

    with patch("videosearch.models.siglip.AutoProcessor") as MockProc, \
         patch("videosearch.models.siglip.AutoModel") as MockMod:
        MockProc.from_pretrained.return_value = mock_processor
        MockMod.from_pretrained.return_value = mock_model
        embedder = SiglipEmbedder("mock-model", device="cpu")

    return embedder, mock_processor, mock_model


def test_embed_images_returns_correct_shape(tmp_path: Path):
    img1 = tmp_path / "a.jpg"
    img2 = tmp_path / "b.jpg"
    Image.new("RGB", (32, 32)).save(img1)
    Image.new("RGB", (32, 32)).save(img2)

    embedder, _, mock_model = _make_embedder()
    mock_model.get_image_features.return_value = torch.randn(2, SIGLIP_DIM)

    result = embedder.embed_images([img1, img2])

    assert len(result) == 2
    assert len(result[0]) == SIGLIP_DIM
    assert len(result[1]) == SIGLIP_DIM


def test_embed_text_returns_correct_shape():
    embedder, _, mock_model = _make_embedder()
    mock_model.get_text_features.return_value = torch.randn(1, SIGLIP_DIM)

    result = embedder.embed_text("a cat on a roof")

    assert len(result) == SIGLIP_DIM
    assert isinstance(result[0], float)
