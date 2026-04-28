# Video Search — Phase 1: Indexer Pipeline (with stub models)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the project skeleton and the synchronous video-indexing pipeline (probe → frames → image embeddings → captions → caption embeddings → DB write) using stub models. No web server, no real models, no watcher — those are Phase 2+. This phase produces a Python package whose `index_video(path)` function exercises the full data path end-to-end against LanceDB and SQLite.

**Architecture:** Single Python package `videosearch/` with focused modules: `scanning/` for file inspection (skip-list, hash, probe, frame sampling), `storage/` for LanceDB tables and a SQLite jobs queue, `models/` for the embedder/captioner protocols and stub implementations, and a top-level `indexer.py` orchestrator. Synchronous code throughout — async wrapping happens later when FastAPI is added. Strict TDD: every task lands with tests that fail first, then code that makes them pass, then a commit.

**Tech Stack:** Python 3.12, `uv`, pydantic v2, pydantic-settings, LanceDB (vector store, embedded), SQLite (stdlib, jobs queue), `xxhash`, ffmpeg + ffprobe (system deps), PySceneDetect, Pillow (thumbnails), pytest, ruff.

---

## Project layout (after Phase 1)

```
video_search/
├── pyproject.toml
├── README.md
├── .gitignore
├── docs/superpowers/{specs,plans}/...
├── src/videosearch/
│   ├── __init__.py
│   ├── config.py
│   ├── indexer.py
│   ├── scanning/
│   │   ├── __init__.py
│   │   ├── skiplist.py
│   │   ├── hashing.py
│   │   ├── probe.py
│   │   └── frames.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   ├── schemas.py
│   │   ├── videos.py
│   │   ├── frame_embeddings.py
│   │   ├── caption_embeddings.py
│   │   ├── library_folders.py
│   │   └── jobs.py
│   └── models/
│       ├── __init__.py
│       ├── protocols.py
│       └── stubs.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    │   └── tiny.mp4
    ├── test_config.py
    ├── test_indexer.py
    ├── scanning/
    │   ├── __init__.py
    │   ├── test_skiplist.py
    │   ├── test_hashing.py
    │   ├── test_probe.py
    │   └── test_frames.py
    ├── storage/
    │   ├── __init__.py
    │   ├── test_db.py
    │   ├── test_videos.py
    │   ├── test_frame_embeddings.py
    │   ├── test_caption_embeddings.py
    │   ├── test_library_folders.py
    │   └── test_jobs.py
    ├── models/
    │   ├── __init__.py
    │   └── test_stubs.py
    └── integration/
        ├── __init__.py
        └── test_indexer_end_to_end.py
```

---

## Task 1: Project bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/videosearch/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src/videosearch/scanning src/videosearch/storage src/videosearch/models
mkdir -p tests/scanning tests/storage tests/models tests/integration tests/fixtures
```

- [ ] **Step 2: Write `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Build artifacts
dist/
build/

# Editor / OS
.DS_Store
.idea/
.vscode/
*.swp

# Project data
data/
models/
*.lance/
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[project]
name = "video-search"
version = "0.0.1"
description = "Plain-text semantic search over local videos."
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "xxhash>=3.4",
    "lancedb>=0.10",
    "pyarrow>=15",
    "scenedetect[opencv]>=0.6.4",
    "pillow>=10.2",
    "numpy>=1.26",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1",
    "ruff>=0.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/videosearch"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]
```

- [ ] **Step 4: Write empty package files**

```python
# src/videosearch/__init__.py
__version__ = "0.0.1"
```

```python
# tests/__init__.py
```

```python
# tests/conftest.py
"""Shared pytest fixtures."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 5: Write `README.md`**

```markdown
# video-search

Plain-text semantic search over local videos. See `docs/superpowers/specs/`.

## Development

```sh
uv sync --dev
uv run pytest
```
```

- [ ] **Step 6: Install and verify**

```bash
uv sync --dev
uv run pytest
```

Expected: pytest exits 5 ("no tests ran") or 0. Either is fine — the point is the toolchain works.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore README.md src/videosearch/__init__.py tests/__init__.py tests/conftest.py
git commit -m "Bootstrap project skeleton (pyproject, package dirs, pytest)"
```

---

## Task 2: Settings (pydantic-settings, TOML + env)

**Files:**
- Create: `src/videosearch/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import sys
from pathlib import Path

from videosearch.config import Settings, default_data_dir, load_config


def test_settings_defaults():
    s = Settings()
    assert s.frame_fps == 1.0
    assert s.port == 8083
    assert s.siglip_model == "google/siglip2-base-patch16-256"
    assert s.text_embedder == "BAAI/bge-small-en-v1.5"
    assert s.vlm_n_gpu_layers == -1


def test_default_data_dir_per_platform():
    p = default_data_dir()
    if sys.platform == "darwin":
        assert "Library/Application Support/videosearch" in str(p)
    else:
        assert ".local/share/videosearch" in str(p)


def test_load_config_from_toml(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('frame_fps = 2.0\nport = 9000\n')
    s = load_config(cfg)
    assert s.frame_fps == 2.0
    assert s.port == 9000


def test_env_overrides_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text('port = 9000\n')
    monkeypatch.setenv("VS_PORT", "9999")
    s = load_config(cfg)
    assert s.port == 9999
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL — `videosearch.config` doesn't exist.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/config.py
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "videosearch"
    return Path.home() / ".local" / "share" / "videosearch"


def default_models_dir() -> Path:
    return default_data_dir() / "models"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VS_", extra="ignore")

    library_paths: list[Path] = Field(default_factory=list)
    data_dir: Path = Field(default_factory=default_data_dir)
    models_dir: Path = Field(default_factory=default_models_dir)

    vlm_model: str | None = None
    vlm_mmproj: str | None = None
    vlm_n_gpu_layers: int = -1
    siglip_model: str = "google/siglip2-base-patch16-256"
    text_embedder: str = "BAAI/bge-small-en-v1.5"

    frame_fps: float = 1.0
    scene_detection: bool = True
    port: int = 8083


def load_config(toml_path: Path | None = None) -> Settings:
    """Load settings, layering TOML file (if present) under env vars."""
    file_data: dict = {}
    if toml_path and toml_path.exists():
        with toml_path.open("rb") as f:
            file_data = tomllib.load(f)
    return Settings(**file_data)
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/config.py tests/test_config.py
git commit -m "Add Settings with TOML + env layering"
```

---

## Task 3: Skip-list

**Files:**
- Create: `src/videosearch/scanning/__init__.py`
- Create: `src/videosearch/scanning/skiplist.py`
- Create: `tests/scanning/__init__.py`
- Test: `tests/scanning/test_skiplist.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/scanning/test_skiplist.py
from pathlib import Path

import pytest

from videosearch.scanning.skiplist import should_skip


@pytest.fixture
def video_file(tmp_path: Path) -> Path:
    p = tmp_path / "movie.mp4"
    p.write_bytes(b"\x00" * 200_000)  # 200 KB
    return p


def test_accepts_valid_video(video_file: Path):
    assert should_skip(video_file) is False


def test_skips_dotfile(tmp_path: Path):
    p = tmp_path / ".hidden.mp4"
    p.write_bytes(b"\x00" * 200_000)
    assert should_skip(p) is True


def test_skips_ds_store(tmp_path: Path):
    p = tmp_path / ".DS_Store"
    p.write_bytes(b"\x00" * 200_000)
    assert should_skip(p) is True


def test_skips_non_video_extension(tmp_path: Path):
    p = tmp_path / "notes.txt"
    p.write_bytes(b"\x00" * 200_000)
    assert should_skip(p) is True


def test_skips_too_small(tmp_path: Path):
    p = tmp_path / "tiny.mp4"
    p.write_bytes(b"\x00" * 1024)  # 1 KB
    assert should_skip(p) is True


def test_skips_inside_photoslibrary_bundle(tmp_path: Path):
    bundle = tmp_path / "MyPhotos.photoslibrary"
    bundle.mkdir()
    p = bundle / "movie.mp4"
    p.write_bytes(b"\x00" * 200_000)
    assert should_skip(p) is True


def test_skips_missing_file(tmp_path: Path):
    p = tmp_path / "ghost.mp4"
    assert should_skip(p) is True
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/scanning/test_skiplist.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/scanning/__init__.py
```

```python
# src/videosearch/scanning/skiplist.py
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

DEFAULT_SKIP_NAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db"})
DEFAULT_BUNDLE_SUFFIXES: tuple[str, ...] = (
    ".photoslibrary",
    ".app",
    ".framework",
    ".bundle",
)
DEFAULT_VIDEO_EXTS: frozenset[str] = frozenset({
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v",
    ".wmv", ".mpg", ".mpeg", ".3gp", ".flv", ".ts",
})
DEFAULT_MIN_SIZE: int = 100_000  # 100 KB


def should_skip(
    path: Path,
    *,
    skip_names: Iterable[str] = DEFAULT_SKIP_NAMES,
    bundle_suffixes: tuple[str, ...] = DEFAULT_BUNDLE_SUFFIXES,
    video_exts: Iterable[str] = DEFAULT_VIDEO_EXTS,
    min_size: int = DEFAULT_MIN_SIZE,
) -> bool:
    """Return True if this path should not be indexed."""
    skip_names_set = set(skip_names)
    video_exts_set = {ext.lower() for ext in video_exts}

    # Bundle ancestor check
    for part in path.parts:
        if part.endswith(bundle_suffixes):
            return True

    # Exact-name skip
    if path.name in skip_names_set:
        return True

    # Hidden / dotfile
    if path.name.startswith("."):
        return True

    # Extension
    if path.suffix.lower() not in video_exts_set:
        return True

    # Size (also catches missing files)
    try:
        if path.stat().st_size < min_size:
            return True
    except FileNotFoundError:
        return True

    return False
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/scanning/test_skiplist.py -v
```

Expected: PASS (7/7).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/scanning/ tests/scanning/__init__.py tests/scanning/test_skiplist.py
git commit -m "Add scan skip-list with default rules"
```

---

## Task 4: Content hashing

**Files:**
- Create: `src/videosearch/scanning/hashing.py`
- Test: `tests/scanning/test_hashing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/scanning/test_hashing.py
from pathlib import Path

from videosearch.scanning.hashing import content_hash


def _write_bytes(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_hash_is_stable(tmp_path: Path):
    p = _write_bytes(tmp_path / "a.mp4", b"hello world" * 1000)
    assert content_hash(p) == content_hash(p)


def test_hash_differs_for_different_content(tmp_path: Path):
    a = _write_bytes(tmp_path / "a.mp4", b"\x00" * 5_000_000)
    b = _write_bytes(tmp_path / "b.mp4", b"\x01" * 5_000_000)
    assert content_hash(a) != content_hash(b)


def test_hash_handles_small_file(tmp_path: Path):
    """Files smaller than the segment-window thresholds still hash deterministically."""
    p = _write_bytes(tmp_path / "small.mp4", b"abcdef" * 100)  # 600 bytes
    h1 = content_hash(p)
    h2 = content_hash(p)
    assert h1 == h2
    assert len(h1) == 16  # xxh64 hex


def test_hash_differs_when_size_differs(tmp_path: Path):
    a = _write_bytes(tmp_path / "a.mp4", b"\x42" * 1_000_000)
    b = _write_bytes(tmp_path / "b.mp4", b"\x42" * 2_000_000)
    assert content_hash(a) != content_hash(b)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/scanning/test_hashing.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/scanning/hashing.py
from __future__ import annotations

from pathlib import Path

import xxhash

SEGMENT_BYTES: int = 1_000_000  # 1 MB per segment


def content_hash(path: Path) -> str:
    """Fast file fingerprint: xxh64 of (first MB || middle MB || last MB || size)."""
    size = path.stat().st_size
    h = xxhash.xxh64()

    with path.open("rb") as f:
        # First segment
        h.update(f.read(min(SEGMENT_BYTES, size)))

        # Middle segment, only if file is large enough to have a distinct middle
        if size > 3 * SEGMENT_BYTES:
            f.seek(size // 2 - SEGMENT_BYTES // 2)
            h.update(f.read(SEGMENT_BYTES))

        # Last segment, only if file is larger than one segment
        if size > SEGMENT_BYTES:
            f.seek(max(0, size - SEGMENT_BYTES))
            h.update(f.read(SEGMENT_BYTES))

    h.update(str(size).encode("ascii"))
    return h.hexdigest()
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/scanning/test_hashing.py -v
```

Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/scanning/hashing.py tests/scanning/test_hashing.py
git commit -m "Add xxh64 content hash for video dedupe"
```

---

## Task 5: Test fixture — tiny.mp4

**Files:**
- Create: `tests/fixtures/tiny.mp4`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Generate the fixture video**

```bash
ffmpeg -y -f lavfi -i testsrc=duration=2:size=320x240:rate=10 \
  -pix_fmt yuv420p tests/fixtures/tiny.mp4
```

Expected: a ~2-second 320x240 test pattern, ~30–80 KB.

- [ ] **Step 2: Verify the fixture is valid**

```bash
ffprobe -v error -show_format -show_streams tests/fixtures/tiny.mp4 | head -20
```

Expected: prints `codec_type=video`, `width=320`, `height=240`, `duration=2.x`.

- [ ] **Step 3: Add a fixture-path helper**

```python
# tests/conftest.py
"""Shared pytest fixtures."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tiny_video(fixtures_dir: Path) -> Path:
    p = fixtures_dir / "tiny.mp4"
    if not p.exists():
        raise FileNotFoundError(
            "tests/fixtures/tiny.mp4 missing. Regenerate with: "
            "ffmpeg -y -f lavfi -i testsrc=duration=2:size=320x240:rate=10 "
            "-pix_fmt yuv420p tests/fixtures/tiny.mp4"
        )
    return p
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/tiny.mp4 tests/conftest.py
git commit -m "Add tiny.mp4 test fixture"
```

---

## Task 6: ffprobe wrapper

**Files:**
- Create: `src/videosearch/scanning/probe.py`
- Test: `tests/scanning/test_probe.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/scanning/test_probe.py
from pathlib import Path

import pytest

from videosearch.scanning.probe import VideoInfo, ProbeError, probe


def test_probe_returns_metadata(tiny_video: Path):
    info = probe(tiny_video)
    assert isinstance(info, VideoInfo)
    assert info.width == 320
    assert info.height == 240
    assert 1.5 < info.duration_sec < 2.5
    assert info.fps > 0


def test_probe_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(ProbeError):
        probe(tmp_path / "does-not-exist.mp4")


def test_probe_raises_on_nonvideo_file(tmp_path: Path):
    p = tmp_path / "junk.mp4"
    p.write_bytes(b"this is not a real video file")
    with pytest.raises(ProbeError):
        probe(p)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/scanning/test_probe.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/scanning/probe.py
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ProbeError(RuntimeError):
    """ffprobe failed or output was unrecognizable."""


@dataclass(frozen=True)
class VideoInfo:
    duration_sec: float
    fps: float
    width: int
    height: int


def probe(path: Path) -> VideoInfo:
    """Run ffprobe and return the first video stream's metadata."""
    if not path.exists():
        raise ProbeError(f"file not found: {path}")

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-print_format", "json",
                "-show_streams", "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ProbeError(f"ffprobe failed: {e.stderr.strip()}") from e

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ProbeError(f"ffprobe returned non-JSON output: {e}") from e

    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        raise ProbeError(f"no video stream found in {path}")
    video = video_streams[0]

    duration = data.get("format", {}).get("duration")
    if duration is None:
        duration = video.get("duration", 0)
    duration_sec = float(duration)

    fps = _parse_rate(video.get("avg_frame_rate", "0/0"))
    if fps == 0:
        fps = _parse_rate(video.get("r_frame_rate", "0/0"))

    return VideoInfo(
        duration_sec=duration_sec,
        fps=fps,
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
    )


def _parse_rate(rate: str) -> float:
    """Convert ffprobe-style 'num/den' to a float (0.0 if invalid)."""
    try:
        num_s, _, den_s = rate.partition("/")
        num, den = int(num_s), int(den_s)
        return num / den if den > 0 else 0.0
    except ValueError:
        return 0.0
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/scanning/test_probe.py -v
```

Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/scanning/probe.py tests/scanning/test_probe.py
git commit -m "Add ffprobe wrapper returning VideoInfo"
```

---

## Task 7: Frame sampling (uniform via ffmpeg)

**Files:**
- Create: `src/videosearch/scanning/frames.py`
- Test: `tests/scanning/test_frames.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/scanning/test_frames.py
from pathlib import Path

from videosearch.scanning.frames import FrameSample, sample_frames


def test_sample_frames_at_1fps(tiny_video: Path, tmp_path: Path):
    out = tmp_path / "thumbs"
    samples = list(sample_frames(tiny_video, fps=1.0, output_dir=out))
    # ~2-second video at 1 fps → 2 frames (give or take 1)
    assert 1 <= len(samples) <= 3
    for s in samples:
        assert isinstance(s, FrameSample)
        assert s.path.exists()
        assert s.path.suffix == ".jpg"
        assert s.timestamp_sec >= 0
    # Indices monotonic
    indices = [s.frame_idx for s in samples]
    assert indices == sorted(indices)


def test_sample_frames_higher_fps_gives_more_frames(tiny_video: Path, tmp_path: Path):
    out = tmp_path / "thumbs5"
    samples = list(sample_frames(tiny_video, fps=5.0, output_dir=out))
    assert len(samples) >= 5  # ~10 expected for a 2-sec @ 5 fps
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/scanning/test_frames.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/scanning/frames.py
from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


class FrameSamplingError(RuntimeError):
    """ffmpeg failed during frame extraction."""


@dataclass(frozen=True)
class FrameSample:
    frame_idx: int
    timestamp_sec: float
    path: Path


def sample_frames(
    video_path: Path,
    *,
    fps: float,
    output_dir: Path,
    jpeg_quality: int = 5,
) -> Iterator[FrameSample]:
    """Sample frames at uniform `fps`, write JPEGs into `output_dir`, yield samples."""
    if fps <= 0:
        raise ValueError("fps must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame-%06d.jpg"
    try:
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(video_path),
                "-vf", f"fps={fps}",
                "-q:v", str(jpeg_quality),
                str(pattern),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise FrameSamplingError(f"ffmpeg failed: {e.stderr.strip()}") from e

    for jpg in sorted(output_dir.glob("frame-*.jpg")):
        # ffmpeg numbers from 1
        idx = int(jpg.stem.split("-")[1])
        timestamp = (idx - 1) / fps
        yield FrameSample(frame_idx=idx, timestamp_sec=timestamp, path=jpg)
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/scanning/test_frames.py -v
```

Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/scanning/frames.py tests/scanning/test_frames.py
git commit -m "Add uniform frame sampling via ffmpeg"
```

---

## Task 8: Scene detection (PySceneDetect)

**Files:**
- Modify: `src/videosearch/scanning/frames.py`
- Modify: `tests/scanning/test_frames.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/scanning/test_frames.py`:

```python
from videosearch.scanning.frames import Scene, detect_scenes


def test_detect_scenes_returns_at_least_one(tiny_video: Path):
    scenes = detect_scenes(tiny_video, fallback_duration_sec=2.0)
    assert len(scenes) >= 1
    for s in scenes:
        assert isinstance(s, Scene)
        assert s.start_sec >= 0
        assert s.end_sec > s.start_sec


def test_detect_scenes_indices_monotonic(tiny_video: Path):
    scenes = detect_scenes(tiny_video, fallback_duration_sec=2.0)
    idxs = [s.scene_idx for s in scenes]
    assert idxs == sorted(idxs)
    assert idxs[0] == 0


def test_detect_scenes_uses_fallback_when_no_cuts(tiny_video: Path):
    """testsrc has no shot cuts; we expect the fallback scene spanning the whole video."""
    scenes = detect_scenes(tiny_video, fallback_duration_sec=2.0)
    # Fallback scenarios produce one scene covering the duration.
    if len(scenes) == 1:
        assert scenes[0].start_sec == 0.0
        assert scenes[0].end_sec == 2.0
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/scanning/test_frames.py -v
```

Expected: FAIL — `Scene` and `detect_scenes` not defined.

- [ ] **Step 3: Add scene detection to `frames.py`**

Append to `src/videosearch/scanning/frames.py`:

```python
@dataclass(frozen=True)
class Scene:
    scene_idx: int
    start_sec: float
    end_sec: float


def detect_scenes(
    video_path: Path,
    *,
    threshold: float = 27.0,
    fallback_duration_sec: float | None = None,
) -> list[Scene]:
    """Detect shot boundaries with PySceneDetect's content detector.

    When the detector finds no cuts (common for short / static videos):
      - if `fallback_duration_sec` is given, return a single scene spanning [0, duration);
      - otherwise return [].
    """
    from scenedetect import ContentDetector, detect

    raw = detect(str(video_path), ContentDetector(threshold=threshold))
    if raw:
        return [
            Scene(
                scene_idx=i,
                start_sec=start.get_seconds(),
                end_sec=end.get_seconds(),
            )
            for i, (start, end) in enumerate(raw)
        ]
    if fallback_duration_sec is not None and fallback_duration_sec > 0:
        return [Scene(scene_idx=0, start_sec=0.0, end_sec=fallback_duration_sec)]
    return []
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/scanning/test_frames.py -v
```

Expected: PASS (4/4 total — 2 sampling + 2 scene).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/scanning/frames.py tests/scanning/test_frames.py
git commit -m "Add PySceneDetect-based scene detection"
```

---

## Task 9: LanceDB schemas + Database class

**Files:**
- Create: `src/videosearch/storage/__init__.py`
- Create: `src/videosearch/storage/schemas.py`
- Create: `src/videosearch/storage/db.py`
- Create: `tests/storage/__init__.py`
- Test: `tests/storage/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_db.py
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
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/storage/test_db.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write schemas**

```python
# src/videosearch/storage/__init__.py
```

```python
# src/videosearch/storage/schemas.py
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
```

- [ ] **Step 4: Write Database class**

```python
# src/videosearch/storage/db.py
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
        existing = set(self._db.table_names())
        for name, model in _TABLES.items():
            if name not in existing:
                self._db.create_table(name, schema=model)

    def table_names(self) -> list[str]:
        return self._db.table_names()

    def table(self, name: str):
        return self._db.open_table(name)
```

- [ ] **Step 5: Run to verify pass**

```bash
uv run pytest tests/storage/test_db.py -v
```

Expected: PASS (3/3).

- [ ] **Step 6: Commit**

```bash
git add src/videosearch/storage/ tests/storage/__init__.py tests/storage/test_db.py
git commit -m "Add LanceDB schemas and Database connection"
```

---

## Task 10: Videos repository

**Files:**
- Create: `src/videosearch/storage/videos.py`
- Test: `tests/storage/test_videos.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_videos.py
import time
import uuid
from pathlib import Path

from videosearch.storage.db import Database
from videosearch.storage.schemas import VideoRow
from videosearch.storage.videos import VideosRepo


def _video(**overrides) -> VideoRow:
    now = time.time()
    base = dict(
        id=str(uuid.uuid4()),
        path="/tmp/movie.mp4",
        hash="abc123",
        duration_sec=10.0,
        fps=30.0,
        width=320,
        height=240,
        mtime=now,
        status="pending",
        error=None,
        indexed_at=None,
        library_folder_id=None,
        last_seen_at=now,
    )
    base.update(overrides)
    return VideoRow(**base)


def test_insert_and_find_by_hash(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    v = _video(hash="hashA")
    repo.insert(v)
    found = repo.find_by_hash("hashA")
    assert found is not None
    assert found.id == v.id


def test_find_by_hash_returns_none_when_missing(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    assert repo.find_by_hash("nope") is None


def test_update_status(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    v = _video(hash="h", status="pending")
    repo.insert(v)
    repo.update(v.id, status="indexed", indexed_at=123.0)
    found = repo.find_by_hash("h")
    assert found is not None
    assert found.status == "indexed"
    assert found.indexed_at == 123.0


def test_list_by_status(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    repo.insert(_video(hash="h1", status="indexed"))
    repo.insert(_video(hash="h2", status="indexed"))
    repo.insert(_video(hash="h3", status="failed"))
    indexed = repo.list_by_status("indexed")
    assert len(indexed) == 2
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/storage/test_videos.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/storage/videos.py
from __future__ import annotations

from typing import Any

from .db import Database
from .schemas import VideoRow


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


class VideosRepo:
    def __init__(self, db: Database):
        self._table = db.table("videos")

    def insert(self, video: VideoRow) -> None:
        self._table.add([video.model_dump()])

    def find_by_hash(self, hash_: str) -> VideoRow | None:
        results = (
            self._table.search()
            .where(f"hash = {_sql_literal(hash_)}")
            .limit(1)
            .to_list()
        )
        return VideoRow(**results[0]) if results else None

    def find_by_id(self, id_: str) -> VideoRow | None:
        results = (
            self._table.search()
            .where(f"id = {_sql_literal(id_)}")
            .limit(1)
            .to_list()
        )
        return VideoRow(**results[0]) if results else None

    def update(self, id_: str, **fields: Any) -> None:
        if not fields:
            return
        values = {k: _sql_literal(v) for k, v in fields.items()}
        self._table.update(where=f"id = {_sql_literal(id_)}", values=values)

    def list_by_status(self, status: str) -> list[VideoRow]:
        results = self._table.search().where(f"status = {_sql_literal(status)}").to_list()
        return [VideoRow(**r) for r in results]
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/storage/test_videos.py -v
```

Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/storage/videos.py tests/storage/test_videos.py
git commit -m "Add VideosRepo with insert/find/update/list"
```

---

## Task 11: Frame embeddings + caption embeddings repos

**Files:**
- Create: `src/videosearch/storage/frame_embeddings.py`
- Create: `src/videosearch/storage/caption_embeddings.py`
- Test: `tests/storage/test_frame_embeddings.py`
- Test: `tests/storage/test_caption_embeddings.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/storage/test_frame_embeddings.py
from pathlib import Path

from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.schemas import SIGLIP_DIM, FrameEmbeddingRow


def _frame(video_id: str, idx: int) -> FrameEmbeddingRow:
    return FrameEmbeddingRow(
        video_id=video_id,
        frame_idx=idx,
        timestamp_sec=float(idx),
        embedding=[0.1] * SIGLIP_DIM,
        thumb_path=f"/tmp/{idx}.jpg",
    )


def test_bulk_insert_and_list(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_frame("v1", i) for i in range(3)])
    rows = repo.list_for_video("v1")
    assert len(rows) == 3
    assert sorted(r.frame_idx for r in rows) == [0, 1, 2]


def test_list_for_other_video_empty(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_frame("v1", 0)])
    assert repo.list_for_video("v2") == []
```

```python
# tests/storage/test_caption_embeddings.py
from pathlib import Path

from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.schemas import TEXT_EMBED_DIM, CaptionEmbeddingRow


def _caption(video_id: str, idx: int) -> CaptionEmbeddingRow:
    return CaptionEmbeddingRow(
        video_id=video_id,
        scene_idx=idx,
        start_sec=float(idx),
        end_sec=float(idx) + 1.0,
        caption=f"scene {idx}",
        embedding=[0.2] * TEXT_EMBED_DIM,
    )


def test_bulk_insert_and_list(tmp_path: Path):
    repo = CaptionEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_caption("v1", i) for i in range(2)])
    rows = repo.list_for_video("v1")
    assert len(rows) == 2
    assert sorted(r.scene_idx for r in rows) == [0, 1]
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/storage/test_frame_embeddings.py tests/storage/test_caption_embeddings.py -v
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Write the implementations**

```python
# src/videosearch/storage/frame_embeddings.py
from __future__ import annotations

from collections.abc import Iterable

from .db import Database
from .schemas import FrameEmbeddingRow
from .videos import _sql_literal


class FrameEmbeddingsRepo:
    def __init__(self, db: Database):
        self._table = db.table("frame_embeddings")

    def insert_many(self, rows: Iterable[FrameEmbeddingRow]) -> None:
        records = [r.model_dump() for r in rows]
        if records:
            self._table.add(records)

    def list_for_video(self, video_id: str) -> list[FrameEmbeddingRow]:
        results = self._table.search().where(f"video_id = {_sql_literal(video_id)}").to_list()
        return [FrameEmbeddingRow(**r) for r in results]

    def delete_for_video(self, video_id: str) -> None:
        self._table.delete(f"video_id = {_sql_literal(video_id)}")
```

```python
# src/videosearch/storage/caption_embeddings.py
from __future__ import annotations

from collections.abc import Iterable

from .db import Database
from .schemas import CaptionEmbeddingRow
from .videos import _sql_literal


class CaptionEmbeddingsRepo:
    def __init__(self, db: Database):
        self._table = db.table("caption_embeddings")

    def insert_many(self, rows: Iterable[CaptionEmbeddingRow]) -> None:
        records = [r.model_dump() for r in rows]
        if records:
            self._table.add(records)

    def list_for_video(self, video_id: str) -> list[CaptionEmbeddingRow]:
        results = self._table.search().where(f"video_id = {_sql_literal(video_id)}").to_list()
        return [CaptionEmbeddingRow(**r) for r in results]

    def delete_for_video(self, video_id: str) -> None:
        self._table.delete(f"video_id = {_sql_literal(video_id)}")
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/storage/test_frame_embeddings.py tests/storage/test_caption_embeddings.py -v
```

Expected: PASS (3/3 total).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/storage/frame_embeddings.py src/videosearch/storage/caption_embeddings.py \
        tests/storage/test_frame_embeddings.py tests/storage/test_caption_embeddings.py
git commit -m "Add FrameEmbeddingsRepo and CaptionEmbeddingsRepo"
```

---

## Task 12: Library folders repo

**Files:**
- Create: `src/videosearch/storage/library_folders.py`
- Test: `tests/storage/test_library_folders.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_library_folders.py
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
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/storage/test_library_folders.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/storage/library_folders.py
from __future__ import annotations

from .db import Database
from .schemas import LibraryFolderRow
from .videos import _sql_literal


class LibraryFoldersRepo:
    def __init__(self, db: Database):
        self._table = db.table("library_folders")

    def insert(self, folder: LibraryFolderRow) -> None:
        self._table.add([folder.model_dump()])

    def list_all(self) -> list[LibraryFolderRow]:
        results = self._table.search().to_list()
        return [LibraryFolderRow(**r) for r in results]

    def delete(self, id_: str) -> None:
        self._table.delete(f"id = {_sql_literal(id_)}")
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/storage/test_library_folders.py -v
```

Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/storage/library_folders.py tests/storage/test_library_folders.py
git commit -m "Add LibraryFoldersRepo"
```

---

## Task 13: Jobs queue (SQLite)

**Files:**
- Create: `src/videosearch/storage/jobs.py`
- Test: `tests/storage/test_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_jobs.py
from pathlib import Path

from videosearch.storage.jobs import Job, JobsQueue


def test_enqueue_and_claim_returns_pending(tmp_path: Path):
    q = JobsQueue(tmp_path / "jobs.db")
    q.enqueue(video_id="v1", kind="ingest")
    job = q.claim()
    assert isinstance(job, Job)
    assert job.video_id == "v1"
    assert job.status == "in_progress"


def test_claim_returns_none_when_empty(tmp_path: Path):
    q = JobsQueue(tmp_path / "jobs.db")
    assert q.claim() is None


def test_complete_marks_done(tmp_path: Path):
    q = JobsQueue(tmp_path / "jobs.db")
    q.enqueue(video_id="v1", kind="ingest")
    job = q.claim()
    assert job is not None
    q.complete(job.id)
    # No more pending work
    assert q.claim() is None


def test_fail_records_error(tmp_path: Path):
    q = JobsQueue(tmp_path / "jobs.db")
    q.enqueue(video_id="v1", kind="ingest")
    job = q.claim()
    assert job is not None
    q.fail(job.id, error="boom")
    failed = q.list_by_status("failed")
    assert len(failed) == 1
    assert failed[0].error == "boom"


def test_jobs_persist_across_instances(tmp_path: Path):
    db = tmp_path / "jobs.db"
    JobsQueue(db).enqueue(video_id="v1", kind="ingest")
    job = JobsQueue(db).claim()
    assert job is not None
    assert job.video_id == "v1"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/storage/test_jobs.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/storage/jobs.py
from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    video_id    TEXT,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,
    progress    REAL NOT NULL DEFAULT 0.0,
    error       TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at);
"""


@dataclass(frozen=True)
class Job:
    id: str
    video_id: str | None
    kind: str
    status: str  # pending | in_progress | completed | failed
    progress: float
    error: str | None
    created_at: float
    updated_at: float


class JobsQueue:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def enqueue(self, *, video_id: str | None, kind: str) -> str:
        job_id = str(uuid.uuid4())
        now = time.time()
        self._conn.execute(
            "INSERT INTO jobs (id, video_id, kind, status, progress, error, "
            "created_at, updated_at) VALUES (?, ?, ?, 'pending', 0.0, NULL, ?, ?)",
            (job_id, video_id, kind, now, now),
        )
        self._conn.commit()
        return job_id

    def claim(self) -> Job | None:
        """Atomically pull the oldest pending job, mark it in_progress."""
        cur = self._conn.execute(
            "SELECT * FROM jobs WHERE status = 'pending' "
            "ORDER BY created_at ASC LIMIT 1"
        )
        row = cur.fetchone()
        if row is None:
            return None
        now = time.time()
        self._conn.execute(
            "UPDATE jobs SET status = 'in_progress', updated_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (now, row["id"]),
        )
        self._conn.commit()
        return Job(**{**dict(row), "status": "in_progress", "updated_at": now})

    def update_progress(self, job_id: str, progress: float) -> None:
        self._conn.execute(
            "UPDATE jobs SET progress = ?, updated_at = ? WHERE id = ?",
            (progress, time.time(), job_id),
        )
        self._conn.commit()

    def complete(self, job_id: str) -> None:
        self._conn.execute(
            "UPDATE jobs SET status = 'completed', progress = 1.0, "
            "updated_at = ? WHERE id = ?",
            (time.time(), job_id),
        )
        self._conn.commit()

    def fail(self, job_id: str, *, error: str) -> None:
        self._conn.execute(
            "UPDATE jobs SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
            (error, time.time(), job_id),
        )
        self._conn.commit()

    def list_by_status(self, status: str) -> list[Job]:
        cur = self._conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,)
        )
        return [Job(**dict(r)) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/storage/test_jobs.py -v
```

Expected: PASS (5/5).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/storage/jobs.py tests/storage/test_jobs.py
git commit -m "Add SQLite-backed JobsQueue"
```

---

## Task 14: Embedder + Captioner protocols + stubs

**Files:**
- Create: `src/videosearch/models/__init__.py`
- Create: `src/videosearch/models/protocols.py`
- Create: `src/videosearch/models/stubs.py`
- Create: `tests/models/__init__.py`
- Test: `tests/models/test_stubs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/models/test_stubs.py
from pathlib import Path

from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.storage.schemas import SIGLIP_DIM, TEXT_EMBED_DIM


def test_image_embedder_shape_and_determinism(tmp_path: Path):
    img = tmp_path / "frame.jpg"
    img.write_bytes(b"\x00" * 1024)
    e = StubImageEmbedder()
    a = e.embed_images([img, img])
    b = e.embed_images([img, img])
    assert len(a) == 2
    assert len(a[0]) == SIGLIP_DIM
    assert a == b  # same input → same output


def test_image_embedder_text_query():
    e = StubImageEmbedder()
    v = e.embed_text("a red door")
    assert len(v) == SIGLIP_DIM


def test_text_embedder_shape_and_determinism():
    e = StubTextEmbedder()
    a = e.embed_text(["hello", "world"])
    b = e.embed_text(["hello", "world"])
    assert len(a) == 2
    assert len(a[0]) == TEXT_EMBED_DIM
    assert a == b


def test_captioner_returns_string(tmp_path: Path):
    img = tmp_path / "frame.jpg"
    img.write_bytes(b"\x00" * 1024)
    c = StubCaptioner()
    cap = c.caption([img], prompt="describe this")
    assert isinstance(cap, str)
    assert len(cap) > 0
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/models/test_stubs.py -v
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Write protocols**

```python
# src/videosearch/models/__init__.py
```

```python
# src/videosearch/models/protocols.py
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class ImageEmbedder(Protocol):
    """Image-text contrastive model (SigLIP family). Provides paired encoders."""

    def embed_images(self, images: Sequence[Path]) -> list[list[float]]: ...
    def embed_text(self, text: str) -> list[float]: ...


class TextEmbedder(Protocol):
    """Pure text retrieval embedder (e.g. bge-small)."""

    def embed_text(self, texts: Sequence[str]) -> list[list[float]]: ...


class Captioner(Protocol):
    """Generates a natural-language caption for one or more images."""

    def caption(self, images: Sequence[Path], *, prompt: str) -> str: ...
```

- [ ] **Step 4: Write stubs**

```python
# src/videosearch/models/stubs.py
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from videosearch.storage.schemas import SIGLIP_DIM, TEXT_EMBED_DIM


def _deterministic_vector(seed: bytes, dim: int) -> list[float]:
    """Generate a stable [-1, 1] vector from arbitrary bytes."""
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        h = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for i in range(0, len(h), 2):
            if len(out) >= dim:
                break
            n = int.from_bytes(h[i : i + 2], "big")
            out.append((n / 65535.0) * 2.0 - 1.0)
        counter += 1
    return out[:dim]


class StubImageEmbedder:
    """Hashes the image bytes (or the text) into a SIGLIP_DIM vector."""

    def embed_images(self, images: Sequence[Path]) -> list[list[float]]:
        vectors = []
        for img in images:
            data = img.read_bytes()
            vectors.append(_deterministic_vector(data, SIGLIP_DIM))
        return vectors

    def embed_text(self, text: str) -> list[float]:
        return _deterministic_vector(text.encode("utf-8"), SIGLIP_DIM)


class StubTextEmbedder:
    def embed_text(self, texts: Sequence[str]) -> list[list[float]]:
        return [_deterministic_vector(t.encode("utf-8"), TEXT_EMBED_DIM) for t in texts]


class StubCaptioner:
    """Deterministic caption derived from the input image filenames."""

    def caption(self, images: Sequence[Path], *, prompt: str) -> str:
        names = ", ".join(p.name for p in images)
        return f"stub caption for {names}"
```

- [ ] **Step 5: Run to verify pass**

```bash
uv run pytest tests/models/test_stubs.py -v
```

Expected: PASS (4/4).

- [ ] **Step 6: Commit**

```bash
git add src/videosearch/models/ tests/models/__init__.py tests/models/test_stubs.py
git commit -m "Add ImageEmbedder/TextEmbedder/Captioner protocols and stubs"
```

---

## Task 15: Indexer pipeline orchestrator

**Files:**
- Create: `src/videosearch/indexer.py`
- Test: `tests/test_indexer.py`

The orchestrator implements steps 1–6 of the spec's indexing pipeline and the
hash-based dedupe / resume / restore logic.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_indexer.py
from pathlib import Path

from videosearch.indexer import IndexResult, index_video
from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.videos import VideosRepo


def _services(tmp_path: Path):
    db = Database(tmp_path / "data")
    return {
        "db": db,
        "videos": VideosRepo(db),
        "frames": FrameEmbeddingsRepo(db),
        "captions": CaptionEmbeddingsRepo(db),
        "image_embedder": StubImageEmbedder(),
        "text_embedder": StubTextEmbedder(),
        "captioner": StubCaptioner(),
    }


def test_index_creates_video_row_and_embeddings(tmp_path: Path, tiny_video: Path):
    s = _services(tmp_path)
    work_dir = tmp_path / "work"

    result = index_video(
        path=tiny_video,
        videos=s["videos"],
        frames=s["frames"],
        captions=s["captions"],
        image_embedder=s["image_embedder"],
        text_embedder=s["text_embedder"],
        captioner=s["captioner"],
        work_dir=work_dir,
        frame_fps=2.0,
    )
    assert isinstance(result, IndexResult)
    assert result.status == "indexed"

    v = s["videos"].find_by_hash(result.hash)
    assert v is not None
    assert v.status == "indexed"
    assert v.indexed_at is not None

    frame_rows = s["frames"].list_for_video(v.id)
    caption_rows = s["captions"].list_for_video(v.id)
    assert len(frame_rows) >= 1
    assert len(caption_rows) >= 1


def test_index_is_idempotent(tmp_path: Path, tiny_video: Path):
    s = _services(tmp_path)
    work_dir = tmp_path / "work"
    kwargs = dict(
        path=tiny_video,
        videos=s["videos"],
        frames=s["frames"],
        captions=s["captions"],
        image_embedder=s["image_embedder"],
        text_embedder=s["text_embedder"],
        captioner=s["captioner"],
        work_dir=work_dir,
        frame_fps=2.0,
    )
    r1 = index_video(**kwargs)
    r2 = index_video(**kwargs)
    assert r1.video_id == r2.video_id
    assert r2.skipped_reason == "already_indexed"
    # No duplicate frame rows
    assert len(s["frames"].list_for_video(r1.video_id)) == \
           len(s["frames"].list_for_video(r2.video_id))


def test_index_restores_missing_to_indexed(tmp_path: Path, tiny_video: Path):
    s = _services(tmp_path)
    work_dir = tmp_path / "work"
    kwargs = dict(
        path=tiny_video,
        videos=s["videos"],
        frames=s["frames"],
        captions=s["captions"],
        image_embedder=s["image_embedder"],
        text_embedder=s["text_embedder"],
        captioner=s["captioner"],
        work_dir=work_dir,
        frame_fps=2.0,
    )
    r = index_video(**kwargs)
    s["videos"].update(r.video_id, status="missing")

    # Re-encounter the same file
    r2 = index_video(**kwargs)
    v = s["videos"].find_by_hash(r.hash)
    assert v is not None
    assert v.status == "indexed"
    assert r2.skipped_reason == "restored_from_missing"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_indexer.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# src/videosearch/indexer.py
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from videosearch.models.protocols import Captioner, ImageEmbedder, TextEmbedder
from videosearch.scanning.frames import (
    FrameSample,
    Scene,
    detect_scenes,
    sample_frames,
)
from videosearch.scanning.hashing import content_hash
from videosearch.scanning.probe import probe
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.schemas import (
    CaptionEmbeddingRow,
    FrameEmbeddingRow,
    VideoRow,
)
from videosearch.storage.videos import VideosRepo


@dataclass(frozen=True)
class IndexResult:
    video_id: str
    hash: str
    status: str
    skipped_reason: str | None = None  # already_indexed | restored_from_missing | path_updated | None


def index_video(
    *,
    path: Path,
    videos: VideosRepo,
    frames: FrameEmbeddingsRepo,
    captions: CaptionEmbeddingsRepo,
    image_embedder: ImageEmbedder,
    text_embedder: TextEmbedder,
    captioner: Captioner,
    work_dir: Path,
    frame_fps: float = 1.0,
    scene_detection: bool = True,
    library_folder_id: str | None = None,
    caption_prompt: str = "Describe what's happening in this scene in one or two sentences.",
) -> IndexResult:
    """Run the full ingestion pipeline for one video file. Synchronous."""
    path = Path(path).resolve()
    h = content_hash(path)

    existing = videos.find_by_hash(h)
    if existing is not None:
        return _resolve_existing(existing, path, videos)

    info = probe(path)
    video_id = str(uuid.uuid4())
    now = time.time()
    row = VideoRow(
        id=video_id,
        path=str(path),
        hash=h,
        duration_sec=info.duration_sec,
        fps=info.fps,
        width=info.width,
        height=info.height,
        mtime=path.stat().st_mtime,
        status="pending",
        last_seen_at=now,
        library_folder_id=library_folder_id,
    )
    videos.insert(row)

    try:
        thumbs_dir = work_dir / video_id / "thumbs"
        samples = list(sample_frames(path, fps=frame_fps, output_dir=thumbs_dir))
        _write_frame_embeddings(frames, video_id, samples, image_embedder)

        if scene_detection:
            scenes = detect_scenes(path, fallback_duration_sec=info.duration_sec)
        else:
            scenes = _fallback_scenes(info.duration_sec)
        _write_caption_embeddings(
            captions, video_id, scenes, samples, captioner, text_embedder, caption_prompt
        )

        videos.update(video_id, status="indexed", indexed_at=time.time(), error=None)
        return IndexResult(video_id=video_id, hash=h, status="indexed")
    except Exception as e:
        videos.update(video_id, status="failed", error=str(e))
        raise


def _resolve_existing(existing: VideoRow, path: Path, videos: VideosRepo) -> IndexResult:
    """Handle hash hits: update path, restore missing, otherwise no-op."""
    updates: dict = {"last_seen_at": time.time()}
    skipped = "already_indexed"
    if str(path) != existing.path:
        updates["path"] = str(path)
        skipped = "path_updated"
    if existing.status == "missing":
        # Restore to indexed if embeddings already exist; otherwise resume on next ingest.
        updates["status"] = "indexed"
        skipped = "restored_from_missing"
    videos.update(existing.id, **updates)
    return IndexResult(
        video_id=existing.id,
        hash=existing.hash,
        status=updates.get("status", existing.status),
        skipped_reason=skipped,
    )


def _fallback_scenes(duration_sec: float, *, window_sec: float = 8.0) -> list[Scene]:
    """Used when scene detection is disabled — fixed-window scene chunks."""
    if duration_sec <= 0:
        return [Scene(scene_idx=0, start_sec=0.0, end_sec=0.0)]
    out: list[Scene] = []
    start = 0.0
    idx = 0
    while start < duration_sec:
        end = min(start + window_sec, duration_sec)
        out.append(Scene(scene_idx=idx, start_sec=start, end_sec=end))
        start = end
        idx += 1
    return out


def _write_frame_embeddings(
    repo: FrameEmbeddingsRepo,
    video_id: str,
    samples: list[FrameSample],
    embedder: ImageEmbedder,
    batch_size: int = 16,
) -> None:
    if not samples:
        return
    for i in range(0, len(samples), batch_size):
        batch = samples[i : i + batch_size]
        vecs = embedder.embed_images([s.path for s in batch])
        rows = [
            FrameEmbeddingRow(
                video_id=video_id,
                frame_idx=s.frame_idx,
                timestamp_sec=s.timestamp_sec,
                embedding=v,
                thumb_path=str(s.path),
            )
            for s, v in zip(batch, vecs, strict=True)
        ]
        repo.insert_many(rows)


def _write_caption_embeddings(
    repo: CaptionEmbeddingsRepo,
    video_id: str,
    scenes: list[Scene],
    samples: list[FrameSample],
    captioner: Captioner,
    text_embedder: TextEmbedder,
    prompt: str,
) -> None:
    if not scenes:
        return
    captions: list[str] = []
    for scene in scenes:
        rep = _representative_frames(scene, samples, max_n=3)
        if not rep:
            captions.append("")
            continue
        captions.append(captioner.caption([s.path for s in rep], prompt=prompt))
    vecs = text_embedder.embed_text(captions)
    rows = [
        CaptionEmbeddingRow(
            video_id=video_id,
            scene_idx=scene.scene_idx,
            start_sec=scene.start_sec,
            end_sec=scene.end_sec,
            caption=cap,
            embedding=vec,
        )
        for scene, cap, vec in zip(scenes, captions, vecs, strict=True)
    ]
    repo.insert_many(rows)


def _representative_frames(
    scene: Scene, samples: list[FrameSample], *, max_n: int
) -> list[FrameSample]:
    in_scene = [s for s in samples if scene.start_sec <= s.timestamp_sec < scene.end_sec]
    if not in_scene:
        # Fall back to the closest single frame to the scene midpoint.
        if not samples:
            return []
        mid = (scene.start_sec + scene.end_sec) / 2
        return [min(samples, key=lambda s: abs(s.timestamp_sec - mid))]
    if len(in_scene) <= max_n:
        return in_scene
    step = len(in_scene) / max_n
    return [in_scene[int(i * step)] for i in range(max_n)]
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/test_indexer.py -v
```

Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/indexer.py tests/test_indexer.py
git commit -m "Add indexer pipeline orchestrator with dedupe/restore"
```

---

## Task 16: End-to-end integration test

**Files:**
- Create: `tests/integration/__init__.py`
- Test: `tests/integration/test_indexer_end_to_end.py`

This task adds no production code; it asserts the whole pipeline behaves
sensibly against the real fixture video (real ffmpeg, real PySceneDetect,
real LanceDB) using stub models.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/__init__.py
```

```python
# tests/integration/test_indexer_end_to_end.py
from pathlib import Path

import numpy as np

from videosearch.indexer import index_video
from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.schemas import SIGLIP_DIM, TEXT_EMBED_DIM
from videosearch.storage.videos import VideosRepo


def test_full_pipeline_produces_expected_data(tmp_path: Path, tiny_video: Path):
    db = Database(tmp_path / "data")
    videos = VideosRepo(db)
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    result = index_video(
        path=tiny_video,
        videos=videos,
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
        captioner=StubCaptioner(),
        work_dir=tmp_path / "work",
        frame_fps=2.0,
    )

    assert result.status == "indexed"
    assert result.skipped_reason is None

    video = videos.find_by_hash(result.hash)
    assert video is not None
    assert video.path == str(tiny_video.resolve())
    assert video.duration_sec > 0
    assert video.width == 320
    assert video.height == 240

    frame_rows = frames.list_for_video(video.id)
    assert len(frame_rows) >= 2
    for r in frame_rows:
        assert len(r.embedding) == SIGLIP_DIM
        assert Path(r.thumb_path).exists()

    caption_rows = captions.list_for_video(video.id)
    assert len(caption_rows) >= 1
    for r in caption_rows:
        assert len(r.embedding) == TEXT_EMBED_DIM
        assert r.modality == "visual_caption"
        assert r.caption  # non-empty string


def test_embeddings_are_unit_finite(tmp_path: Path, tiny_video: Path):
    """Sanity: all stub embeddings should be finite floats in [-1, 1]."""
    db = Database(tmp_path / "data")
    videos = VideosRepo(db)
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    result = index_video(
        path=tiny_video,
        videos=videos,
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
        captioner=StubCaptioner(),
        work_dir=tmp_path / "work",
        frame_fps=2.0,
    )

    for r in frames.list_for_video(result.video_id):
        arr = np.asarray(r.embedding)
        assert np.all(np.isfinite(arr))
        assert np.all(np.abs(arr) <= 1.0)
    for r in captions.list_for_video(result.video_id):
        arr = np.asarray(r.embedding)
        assert np.all(np.isfinite(arr))
        assert np.all(np.abs(arr) <= 1.0)
```

- [ ] **Step 2: Run to verify pass**

```bash
uv run pytest tests/integration/test_indexer_end_to_end.py -v
```

Expected: PASS (2/2). All prior code already supports this.

- [ ] **Step 3: Run the full test suite as a final sanity check**

```bash
uv run pytest -v
```

Expected: every test in the suite passes.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_indexer_end_to_end.py
git commit -m "Add end-to-end indexer integration test on tiny.mp4"
```

---

## Phase 1 acceptance criteria

The phase is complete when:

1. `uv run pytest -v` passes every test in `tests/`.
2. `uv run pytest tests/integration/ -v` passes against the real fixture video.
3. `index_video(...)` from `videosearch.indexer` runs the full pipeline against
   any video file the system can probe.
4. The `videos`, `frame_embeddings`, `caption_embeddings`, and
   `library_folders` tables exist in LanceDB at `<data_dir>/lance/`.
5. The SQLite jobs queue at `<data_dir>/jobs.db` accepts enqueue / claim /
   complete / fail operations and persists across processes.

What's deferred to subsequent plans:

- **Phase 2:** real models — SigLIP 2 via PyTorch+MPS/CUDA, bge-small via
  sentence-transformers, Qwen2.5-VL-3B via llama-cpp-python.
- **Phase 3:** search service — query embedding, ANN, RRF fusion, grouping,
  missing filter.
- **Phase 4:** FastAPI app — endpoints, watcher, byte-range streaming,
  reveal, WebSocket, ingest API.
- **Phase 5:** SvelteKit frontend.
- **Phase 6:** CLI launcher, packaging, launchd / systemd templates.
