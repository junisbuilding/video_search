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
