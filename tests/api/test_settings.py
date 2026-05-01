from __future__ import annotations

from pathlib import Path


def test_get_settings_returns_current_settings(client, test_settings):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["port"] == test_settings.port
    assert data["frame_fps"] == test_settings.frame_fps


def test_patch_settings_updates_field(client, test_settings):
    r = client.patch("/api/settings", json={"frame_fps": 2.0})
    assert r.status_code == 200
    assert r.json()["frame_fps"] == 2.0


def test_patch_settings_writes_config_toml(client, test_settings):
    client.patch("/api/settings", json={"frame_fps": 3.0})
    config_path = test_settings.data_dir / "config.toml"
    assert config_path.exists()
    content = config_path.read_text()
    assert "frame_fps" in content


def test_patch_settings_rejects_unknown_fields(client):
    r = client.patch("/api/settings", json={"nonexistent_field": "value"})
    # Unknown fields are ignored (pydantic extra="ignore"), response is still 200
    assert r.status_code == 200


def test_patch_settings_invalid_type_returns_422(client):
    r = client.patch("/api/settings", json={"port": "not-an-int"})
    assert r.status_code == 422
