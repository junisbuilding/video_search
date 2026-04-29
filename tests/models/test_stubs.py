from pathlib import Path

from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.storage.schemas import SIGLIP_DIM, TEXT_EMBED_DIM


def test_image_embedder_shape_and_determinism(tmp_path: Path):
    img = tmp_path / "frame.jpg"
    img.write_bytes(b"\x00" * 1024)
    e = StubImageEmbedder()
    a = e.embed_images([img, img])
    b = e.embed_images([img, img])
    assert len(a) == 2
    assert len(a[0]) == SIGLIP_DIM
    assert a == b  # same input → same output


def test_image_embedder_text_query():
    e = StubImageEmbedder()
    v = e.embed_text("a red door")
    assert len(v) == SIGLIP_DIM


def test_text_embedder_shape_and_determinism():
    e = StubTextEmbedder()
    a = e.embed_text(["hello", "world"])
    b = e.embed_text(["hello", "world"])
    assert len(a) == 2
    assert len(a[0]) == TEXT_EMBED_DIM
    assert a == b


def test_captioner_returns_string(tmp_path: Path):
    img = tmp_path / "frame.jpg"
    img.write_bytes(b"\x00" * 1024)
    c = StubCaptioner()
    cap = c.caption([img], prompt="describe this")
    assert isinstance(cap, str)
    assert len(cap) > 0
