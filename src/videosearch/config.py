from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "videosearch"
    return Path.home() / ".local" / "share" / "videosearch"


def default_models_dir() -> Path:
    return default_data_dir() / "models"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VS_", extra="ignore")

    library_paths: list[Path] = Field(default_factory=list)
    data_dir: Path = Field(default_factory=default_data_dir)
    models_dir: Path = Field(default_factory=default_models_dir)

    vlm_model: str | None = None
    vlm_mmproj: str | None = None
    vlm_n_gpu_layers: int = -1
    siglip_model: str = "google/siglip2-base-patch16-256"
    text_embedder: str = "BAAI/bge-small-en-v1.5"

    frame_fps: float = 1.0
    scene_detection: bool = True
    port: int = 8083


def load_config(toml_path: Path | None = None) -> Settings:
    """Load settings, layering TOML file (if present) under env vars.

    Environment variables (VS_* prefix) take precedence over TOML file values.
    """
    import os

    file_data: dict = {}
    if toml_path and toml_path.exists():
        with toml_path.open("rb") as f:
            file_data = tomllib.load(f)

    # Read env vars manually to ensure they take precedence over file data
    env_data = {}
    for field_name in Settings.model_fields:
        env_key = f"VS_{field_name.upper()}"
        if env_key in os.environ:
            env_data[field_name] = os.environ[env_key]

    # Merge: file_data < env_data (env vars win)
    merged_data = {**file_data, **env_data}

    return Settings(**merged_data)
