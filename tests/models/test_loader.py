from pathlib import Path
from unittest.mock import patch

import pytest

from videosearch.models.loader import resolve_gguf


def test_resolve_local_path(tmp_path: Path):
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"fake")

    result = resolve_gguf(str(gguf), cache_dir=tmp_path)

    assert result == gguf


def test_resolve_hf_spec(tmp_path: Path):
    spec = "bartowski/Qwen2.5-VL-3B-Instruct-GGUF::Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
    fake_path = tmp_path / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
    fake_path.write_bytes(b"fake")

    with patch("videosearch.models.loader.hf_hub_download", return_value=str(fake_path)) as mock_dl:
        result = resolve_gguf(spec, cache_dir=tmp_path)

    mock_dl.assert_called_once_with(
        "bartowski/Qwen2.5-VL-3B-Instruct-GGUF",
        "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
        cache_dir=str(tmp_path),
    )
    assert result == fake_path


def test_resolve_missing_local_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_gguf(str(tmp_path / "nonexistent.gguf"), cache_dir=tmp_path)
