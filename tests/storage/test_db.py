from pathlib import Path

from videosearch.storage.db import Database


def test_database_creates_all_tables(tmp_path: Path):
    db = Database(tmp_path)
    names = set(db.table_names())
    assert {"videos", "frame_embeddings", "caption_embeddings", "library_folders"} <= names


def test_database_idempotent_on_reopen(tmp_path: Path):
    Database(tmp_path)
    db2 = Database(tmp_path)
    names = set(db2.table_names())
    assert {"videos", "frame_embeddings", "caption_embeddings", "library_folders"} <= names


def test_database_creates_data_dir(tmp_path: Path):
    target = tmp_path / "nested" / "videosearch"
    Database(target)
    assert target.exists()
    assert (target / "lance").exists()
