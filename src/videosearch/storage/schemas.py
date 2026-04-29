from __future__ import annotations

from lancedb.pydantic import LanceModel, Vector

# Default-model dimensions. Stubs in tests must produce vectors of these sizes
# so the schema is identical between stub and real-model runs.
SIGLIP_DIM: int = 768
TEXT_EMBED_DIM: int = 384


class VideoRow(LanceModel):
    id: str
    path: str
    hash: str
    duration_sec: float
    fps: float
    width: int
    height: int
    mtime: float
    status: str  # pending | indexed | failed | missing
    error: str | None = None
    indexed_at: float | None = None
    library_folder_id: str | None = None
    last_seen_at: float


class FrameEmbeddingRow(LanceModel):
    video_id: str
    frame_idx: int
    timestamp_sec: float
    embedding: Vector(SIGLIP_DIM)
    thumb_path: str


class CaptionEmbeddingRow(LanceModel):
    video_id: str
    scene_idx: int
    start_sec: float
    end_sec: float
    caption: str
    embedding: Vector(TEXT_EMBED_DIM)
    modality: str = "visual_caption"


class LibraryFolderRow(LanceModel):
    id: str
    path: str
    added_at: float
