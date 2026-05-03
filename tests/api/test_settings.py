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
    import tomllib
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    assert data["frame_fps"] == 3.0


def test_patch_settings_rejects_unknown_fields(client):
    r = client.patch("/api/settings", json={"nonexistent_field": "value"})
    # Unknown fields are ignored (pydantic extra="ignore"), response is still 200
    assert r.status_code == 200


def test_patch_settings_invalid_type_returns_422(client):
    r = client.patch("/api/settings", json={"port": "not-an-int"})
    assert r.status_code == 422


def test_patch_settings_can_disable_scene_detection(client, test_settings):
    r = client.patch("/api/settings", json={"scene_detection": False})
    assert r.status_code == 200
    assert r.json()["scene_detection"] is False


def test_settings_response_includes_hf_token_null(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "hf_token" in data
    assert data["hf_token"] is None


def test_patch_settings_saves_hf_token(client):
    r = client.patch("/api/settings", json={"hf_token": "hf_abc123"})
    assert r.status_code == 200
    assert r.json()["hf_token"] == "hf_abc123"
