from __future__ import annotations


def test_ingest_single_file(client, mock_jobs, tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x" * 200_000)

    r = client.post("/api/ingest", json={"path": str(f)})

    assert r.status_code == 200
    data = r.json()
    assert len(data["enqueued"]) == 1
    mock_jobs.enqueue.assert_called_once()


def test_ingest_directory_recursive(client, mock_jobs, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.mp4").write_bytes(b"x" * 200_000)
    (sub / "b.mp4").write_bytes(b"x" * 200_000)

    r = client.post("/api/ingest", json={"path": str(tmp_path), "recursive": True})

    assert r.status_code == 200
    assert len(r.json()["enqueued"]) == 2


def test_ingest_directory_non_recursive(client, mock_jobs, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.mp4").write_bytes(b"x" * 200_000)
    (sub / "b.mp4").write_bytes(b"x" * 200_000)

    r = client.post("/api/ingest", json={"path": str(tmp_path), "recursive": False})

    assert r.status_code == 200
    assert len(r.json()["enqueued"]) == 1


def test_ingest_nonexistent_path_returns_400(client):
    r = client.post("/api/ingest", json={"path": "/no/such/file.mp4"})
    assert r.status_code == 400
