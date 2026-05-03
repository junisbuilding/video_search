import sys
from pathlib import Path

from videosearch.config import Settings, default_data_dir, load_config


def test_settings_defaults():
    s = Settings()
    assert s.frame_fps == 1.0
    assert s.port == 8083
    assert s.siglip_model == "google/siglip2-base-patch16-256"
    assert s.text_embedder == "BAAI/bge-small-en-v1.5"
    assert s.vlm_n_gpu_layers == -1


def test_default_data_dir_per_platform():
    p = default_data_dir()
    if sys.platform == "darwin":
        assert "Library/Application Support/videosearch" in str(p)
    else:
        assert ".local/share/videosearch" in str(p)


def test_load_config_from_toml(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('frame_fps = 2.0\nport = 9000\n')
    s = load_config(cfg)
    assert s.frame_fps == 2.0
    assert s.port == 9000


def test_env_overrides_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text('port = 9000\n')
    monkeypatch.setenv("VS_PORT", "9999")
    s = load_config(cfg)
    assert s.port == 9999


def test_hf_token_defaults_to_none():
    s = load_config()
    assert s.hf_token is None


def test_hf_token_from_hf_token_env(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_abc")
    monkeypatch.delenv("VS_HF_TOKEN", raising=False)
    s = load_config()
    assert s.hf_token == "hf_abc"


def test_vs_hf_token_overrides_hf_token(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_from_bare")
    monkeypatch.setenv("VS_HF_TOKEN", "hf_from_vs")
    s = load_config()
    assert s.hf_token == "hf_from_vs"
