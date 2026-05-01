from __future__ import annotations

from pathlib import Path

import videosearch.api.routers.fs as fs_module


def test_fs_list_defaults_to_home(client):
    r = client.get("/api/fs/list")
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == str(Path.home().resolve())


def test_fs_list_returns_entries(client, tmp_path, monkeypatch):
    monkeypatch.setattr(fs_module, "_HOME", tmp_path)
    (tmp_path / "Movies").mkdir()
    (tmp_path / "clip.mp4").write_bytes(b"x" * 200_000)
    (tmp_path / "notes.txt").write_bytes(b"text")

    r = client.get(f"/api/fs/list?path={tmp_path}")
    assert r.status_code == 200
    entries = {e["name"]: e for e in r.json()["entries"]}
    assert "Movies" in entries
    assert entries["Movies"]["kind"] == "dir"
    assert "clip.mp4" in entries
    assert entries["clip.mp4"]["kind"] == "video"
    assert "notes.txt" in entries
    assert entries["notes.txt"]["kind"] == "other"


def test_fs_list_excludes_hidden_files(client, tmp_path, monkeypatch):
    monkeypatch.setattr(fs_module, "_HOME", tmp_path)
    (tmp_path / ".hidden").write_bytes(b"x")
    (tmp_path / "visible.mp4").write_bytes(b"x" * 200_000)

    r = client.get(f"/api/fs/list?path={tmp_path}")
    names = [e["name"] for e in r.json()["entries"]]
    assert ".hidden" not in names
    assert "visible.mp4" in names


def test_fs_list_rejects_path_outside_home(client):
    home = Path.home().resolve()
    outside = Path("/tmp").resolve()
    if str(outside).startswith(str(home)):
        return  # skip — /tmp is inside home on this system
    r = client.get("/api/fs/list?path=/tmp")
    assert r.status_code == 403


def test_fs_list_returns_parent(client):
    home = Path.home().resolve()
    r = client.get(f"/api/fs/list?path={home}")
    data = r.json()
    assert "parent" in data
