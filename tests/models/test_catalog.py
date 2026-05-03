from __future__ import annotations

import pytest
from videosearch.models.catalog import CATALOG, ModelEntry, find_by_id, get_default


def test_each_type_has_exactly_one_default():
    for model_type, entries in CATALOG.items():
        defaults = [e for e in entries if e.default]
        assert len(defaults) == 1, f"{model_type} must have exactly one default"


def test_all_entries_have_ids():
    for model_type, entries in CATALOG.items():
        for e in entries:
            assert e.id, f"{model_type} entry missing id"
            assert e.label, f"{model_type} entry missing label"
            assert e.size_label, f"{model_type} entry missing size_label"


def test_vision_entries_have_gguf_specs():
    for e in CATALOG["vision"]:
        assert e.vlm_model and "::" in e.vlm_model
        assert e.vlm_mmproj and "::" in e.vlm_mmproj
        assert e.hf_repo is None


def test_siglip_and_text_embedder_have_hf_repo():
    for model_type in ("siglip", "text_embedder"):
        for e in CATALOG[model_type]:
            assert e.hf_repo
            assert e.vlm_model is None
            assert e.vlm_mmproj is None


def test_find_by_id_returns_entry():
    entry = find_by_id("siglip", "siglip2-base")
    assert entry is not None
    assert entry.id == "siglip2-base"


def test_find_by_id_returns_none_for_unknown():
    assert find_by_id("vision", "does-not-exist") is None
    assert find_by_id("nonexistent_type", "x") is None


def test_get_default_returns_default_entry():
    entry = get_default("text_embedder")
    assert entry.default is True


def test_get_default_raises_for_unknown_type():
    with pytest.raises(KeyError):
        get_default("bogus")
