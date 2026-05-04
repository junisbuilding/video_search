from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from videosearch.api.deps import get_downloader, get_settings
from videosearch.config import Settings
from videosearch.models.catalog import CATALOG, ModelEntry, find_by_id
from videosearch.models.downloader import DownloadProgress, ModelDownloader

router = APIRouter()


class CatalogEntryOut(BaseModel):
    id: str
    label: str
    size_label: str
    cached: bool
    default: bool


class CatalogResponse(BaseModel):
    first_run: bool
    active_models: dict[str, str]
    vision: list[CatalogEntryOut]
    siglip: list[CatalogEntryOut]
    text_embedder: list[CatalogEntryOut]


class DownloadRequest(BaseModel):
    model_type: str
    model_id: str


class DownloadResponse(BaseModel):
    queued: bool
    reason: str = ""


def _build_entry_out(model_type: str, entry: ModelEntry, downloader: ModelDownloader) -> CatalogEntryOut:
    return CatalogEntryOut(
        id=entry.id,
        label=entry.label,
        size_label=entry.size_label,
        cached=downloader.is_cached(model_type, entry.id),
        default=entry.default,
    )


def _active_model_id(model_type: str, settings: Settings) -> str:
    if model_type == "vision":
        raw = settings.vlm_model
        if not raw:
            return ""
        for entry in CATALOG["vision"]:
            if entry.vlm_model == raw:
                return entry.id
    elif model_type == "siglip":
        raw = settings.siglip_model
        if not raw:
            return ""
        for entry in CATALOG["siglip"]:
            if entry.hf_repo == raw:
                return entry.id
    elif model_type == "text_embedder":
        raw = settings.text_embedder
        if not raw:
            return ""
        for entry in CATALOG["text_embedder"]:
            if entry.hf_repo == raw:
                return entry.id
    return ""


@router.get("/models/catalog", response_model=CatalogResponse)
async def get_catalog(
    settings: Settings = Depends(get_settings),
    downloader: ModelDownloader = Depends(get_downloader),
) -> CatalogResponse:
    vision_out = [_build_entry_out("vision", e, downloader) for e in CATALOG["vision"]]
    siglip_out = [_build_entry_out("siglip", e, downloader) for e in CATALOG["siglip"]]
    te_out = [_build_entry_out("text_embedder", e, downloader) for e in CATALOG["text_embedder"]]

    first_run = not (
        any(e.cached for e in vision_out)
        and any(e.cached for e in siglip_out)
        and any(e.cached for e in te_out)
    )

    active_models = {
        "vision": _active_model_id("vision", settings),
        "siglip": _active_model_id("siglip", settings),
        "text_embedder": _active_model_id("text_embedder", settings),
    }

    return CatalogResponse(
        first_run=first_run,
        active_models=active_models,
        vision=vision_out,
        siglip=siglip_out,
        text_embedder=te_out,
    )


@router.post("/models/download", response_model=DownloadResponse)
async def start_download(
    body: DownloadRequest,
    downloader: ModelDownloader = Depends(get_downloader),
) -> DownloadResponse:
    if find_by_id(body.model_type, body.model_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model: {body.model_type}/{body.model_id}",
        )
    if downloader.is_cached(body.model_type, body.model_id):
        return DownloadResponse(queued=False, reason="already_cached")
    queued = await downloader.enqueue(body.model_type, body.model_id)
    return DownloadResponse(queued=queued, reason="" if queued else "already_running")


@router.get("/models/download/progress", response_model=list[DownloadProgress])
async def get_progress(
    downloader: ModelDownloader = Depends(get_downloader),
) -> list[DownloadProgress]:
    return downloader.progress()
