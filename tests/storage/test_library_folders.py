import time
import uuid
from pathlib import Path

from videosearch.storage.db import Database
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.schemas import LibraryFolderRow


def _folder(path: str) -> LibraryFolderRow:
    return LibraryFolderRow(id=str(uuid.uuid4()), path=path, added_at=time.time())


def test_insert_and_list(tmp_path: Path):
    repo = LibraryFoldersRepo(Database(tmp_path))
    repo.insert(_folder("/movies"))
    repo.insert(_folder("/clips"))
    rows = repo.list_all()
    assert {r.path for r in rows} == {"/movies", "/clips"}


def test_delete_by_id(tmp_path: Path):
    repo = LibraryFoldersRepo(Database(tmp_path))
    f = _folder("/movies")
    repo.insert(f)
    repo.delete(f.id)
    assert repo.list_all() == []


def _make_folder(id_: str, path: str = "/movies") -> LibraryFolderRow:
    return LibraryFolderRow(id=id_, path=path, added_at=time.time())


def test_find_by_id_returns_folder(tmp_path):
    db = Database(tmp_path / "data")
    repo = LibraryFoldersRepo(db)
    repo.insert(_make_folder("f1", "/movies"))
    result = repo.find_by_id("f1")
    assert result is not None
    assert result.id == "f1"
    assert result.path == "/movies"


def test_find_by_id_returns_none_when_missing(tmp_path):
    db = Database(tmp_path / "data")
    repo = LibraryFoldersRepo(db)
    assert repo.find_by_id("nonexistent") is None
