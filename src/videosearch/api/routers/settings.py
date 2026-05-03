from __future__ import annotations

from pathlib import Path

import tomli_w
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from videosearch.api.deps import get_settings
from videosearch.config import Settings

router = APIRouter()


def _settings_to_dict(s: Settings, include_none_hf_token: bool = False) -> dict:
    """Convert settings to dict for API or TOML output.

    Args:
        s: Settings object
        include_none_hf_token: If True, include hf_token even when None (for API responses).
                              If False, skip None values (for TOML output).
    """
    result: dict = {}
    for key, value in s.model_dump().items():
        if key == "hf_token":
            continue  # handled explicitly below
        if value is None:
            continue
        if isinstance(value, Path):
            result[key] = str(value)
        elif isinstance(value, list):
            result[key] = [str(item) if isinstance(item, Path) else item for item in value]
        else:
            result[key] = value

    # Handle hf_token: always include in API response, skip in TOML if None
    if include_none_hf_token or s.hf_token is not None:
        result["hf_token"] = s.hf_token

    return result


@router.get("/settings")
async def get_settings_endpoint(
    settings: Settings = Depends(get_settings),
) -> dict:
    return _settings_to_dict(settings, include_none_hf_token=True)


class SettingsPatch(BaseModel, extra="ignore"):
    frame_fps: float | None = None
    scene_detection: bool | None = None
    port: int | None = None
    siglip_model: str | None = None
    text_embedder: str | None = None
    vlm_model: str | None = None
    vlm_mmproj: str | None = None
    vlm_n_gpu_layers: int | None = None
    hf_token: str | None = None


@router.patch("/settings")
async def patch_settings(
    request: Request,
    body: SettingsPatch,
    settings: Settings = Depends(get_settings),
) -> dict:
    current = settings.model_dump()
    patch = {k: body.model_dump()[k] for k in body.model_fields_set}
    current.update(patch)
    new_settings = Settings(**current)

    config_path = Path(new_settings.data_dir) / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "wb") as f:
        tomli_w.dump(_settings_to_dict(new_settings, include_none_hf_token=False), f)

    request.app.state.settings = new_settings
    return _settings_to_dict(new_settings, include_none_hf_token=True)
