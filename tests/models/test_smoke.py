"""
Real-model smoke tests. Run with: uv run pytest -m smoke -v

SigLIP and BGE download from HF Hub automatically on first run (~750 MB total).
VLM requires VS_VLM_MODEL and VS_VLM_MMPROJ to be set (see plan header).
"""
from pathlib import Path

import pytest
from PIL import Image

from videosearch.config import load_config
from videosearch.models.bge import BgeTextEmbedder
from videosearch.models.llama_cpp_captioner import LlamaCppCaptioner
from videosearch.models.loader import resolve_gguf
from videosearch.models.siglip import SiglipEmbedder
from videosearch.storage.schemas import SIGLIP_DIM, TEXT_EMBED_DIM


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def test_image(tmp_path_factory) -> Path:
    img = tmp_path_factory.mktemp("smoke") / "frame.jpg"
    Image.new("RGB", (256, 256), color=(100, 149, 237)).save(img)
    return img


@pytest.mark.smoke
def test_siglip_image_embedding_shape(cfg, test_image):
    embedder = SiglipEmbedder(cfg.siglip_model)
    vecs = embedder.embed_images([test_image])

    assert len(vecs) == 1
    assert len(vecs[0]) == SIGLIP_DIM


@pytest.mark.smoke
def test_siglip_text_embedding_shape(cfg):
    embedder = SiglipEmbedder(cfg.siglip_model)
    vec = embedder.embed_text("a colorful abstract image")

    assert len(vec) == SIGLIP_DIM


@pytest.mark.smoke
def test_bge_embedding_shape(cfg):
    embedder = BgeTextEmbedder(cfg.text_embedder)
    vecs = embedder.embed_text(["hello world", "second sentence"])

    assert len(vecs) == 2
    assert len(vecs[0]) == TEXT_EMBED_DIM


@pytest.mark.smoke
def test_llama_cpp_captioner(cfg, test_image):
    if not cfg.vlm_model or not cfg.vlm_mmproj:
        pytest.skip("VS_VLM_MODEL and VS_VLM_MMPROJ not set")

    model_path = resolve_gguf(cfg.vlm_model, cache_dir=cfg.models_dir)
    mmproj_path = resolve_gguf(cfg.vlm_mmproj, cache_dir=cfg.models_dir)

    captioner = LlamaCppCaptioner(str(model_path), str(mmproj_path))
    result = captioner.caption(
        [test_image],
        prompt="Describe this image in one sentence.",
    )

    assert isinstance(result, str)
    assert len(result) > 5
