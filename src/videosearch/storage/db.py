from __future__ import annotations

from pathlib import Path

import lancedb

from .schemas import (
    CaptionEmbeddingRow,
    FrameEmbeddingRow,
    LibraryFolderRow,
    VideoRow,
)

_TABLES: dict[str, type] = {
    "videos": VideoRow,
    "frame_embeddings": FrameEmbeddingRow,
    "caption_embeddings": CaptionEmbeddingRow,
    "library_folders": LibraryFolderRow,
}


class Database:
    """LanceDB connection rooted at <data_dir>/lance with all required tables created."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lance_dir = self.data_dir / "lance"
        self._db = lancedb.connect(str(self.lance_dir))
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        existing = set(self._db.list_tables().tables)
        for name, model in _TABLES.items():
            if name not in existing:
                self._db.create_table(name, schema=model)

    def table_names(self) -> list[str]:
        return self._db.list_tables().tables

    def table(self, name: str):
        return self._db.open_table(name)
