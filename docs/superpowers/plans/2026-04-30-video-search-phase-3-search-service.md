# Video Search Phase 3: Search Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `Searcher` class that accepts a natural-language query, embeds it with both models, runs ANN search on frames and captions, fuses results with RRF, and returns a ranked list of `VideoResult` objects with timestamped `Moment` entries.

**Architecture:** New `src/videosearch/search/` package with three modules: `models.py` (frozen dataclasses), `rrf.py` (pure fusion function), `searcher.py` (orchestrator). Two storage repos get vector-search methods. No external dependencies added.

**Tech Stack:** LanceDB ANN search (`.search(vector).limit(k).to_list()`), Python dataclasses, pytest.

---

## File Structure

**Create:**
- `src/videosearch/search/__init__.py` — re-exports `Searcher`, `SearchResponse`, `VideoResult`, `Moment`
- `src/videosearch/search/models.py` — `Moment`, `VideoResult`, `SearchResponse` frozen dataclasses
- `src/videosearch/search/rrf.py` — `rrf_fuse(ranked_lists, *, k=60) -> list[tuple[str, float]]`
- `src/videosearch/search/searcher.py` — `Searcher` class
- `tests/search/__init__.py` — empty, for test discovery
- `tests/search/test_models.py`
- `tests/search/test_rrf.py`
- `tests/search/test_searcher.py`
- `tests/search/test_search_integration.py`

**Modify:**
- `src/videosearch/storage/frame_embeddings.py` — add `search()` and `find_nearest()`
- `src/videosearch/storage/caption_embeddings.py` — add `search()`
- `tests/storage/test_frame_embeddings.py` — add search and find_nearest tests
- `tests/storage/test_caption_embeddings.py` — add search test

---

### Task 1: Data models

**Files:**
- Create: `src/videosearch/search/__init__.py`
- Create: `src/videosearch/search/models.py`
- Create: `tests/search/__init__.py`
- Create: `tests/search/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/search/test_models.py
from videosearch.search.models import Moment, SearchResponse, VideoResult


def test_moment_construction():
    m = Moment(timestamp_sec=1.5, score=0.8, thumb_path="/tmp/t.jpg", caption=None)
    assert m.timestamp_sec == 1.5
    assert m.score == 0.8
    assert m.thumb_path == "/tmp/t.jpg"
    assert m.caption is None


def test_moment_with_caption():
    m = Moment(timestamp_sec=2.0, score=0.5, thumb_path=None, caption="a scene")
    assert m.caption == "a scene"
    assert m.thumb_path is None


def test_video_result_construction():
    moments = [Moment(timestamp_sec=1.0, score=0.9, thumb_path=None, caption=None)]
    vr = VideoResult(video_id="v1", top_score=0.9, moments=moments)
    assert vr.video_id == "v1"
    assert vr.top_score == 0.9
    assert len(vr.moments) == 1


def test_search_response_construction():
    vr = VideoResult(video_id="v1", top_score=0.7, moments=[])
    resp = SearchResponse(query="cats", results=[vr])
    assert resp.query == "cats"
    assert len(resp.results) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```
cd /mnt/c/Users/jun/code/video_search
uv run pytest tests/search/test_models.py -v
```

Expected: ERROR — `ModuleNotFoundError: No module named 'videosearch.search'`

- [ ] **Step 3: Create the package and models**

```python
# tests/search/__init__.py
# (empty)
```

```python
# src/videosearch/search/models.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Moment:
    timestamp_sec: float
    score: float
    thumb_path: str | None
    caption: str | None = None


@dataclass(frozen=True)
class VideoResult:
    video_id: str
    top_score: float
    moments: list[Moment]


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: list[VideoResult]
```

```python
# src/videosearch/search/__init__.py
from .models import Moment, SearchResponse, VideoResult
from .searcher import Searcher

__all__ = ["Moment", "SearchResponse", "Searcher", "VideoResult"]
```

Note: `__init__.py` imports `Searcher` from a module that does not exist yet. For now, write the `__init__.py` without the `Searcher` import and add it in Task 4:

```python
# src/videosearch/search/__init__.py  (Task 1 version — Searcher added in Task 4)
from .models import Moment, SearchResponse, VideoResult

__all__ = ["Moment", "SearchResponse", "VideoResult"]
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/search/test_models.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/search/__init__.py src/videosearch/search/models.py tests/search/__init__.py tests/search/test_models.py
git commit -m "feat(search): add Moment, VideoResult, SearchResponse data models"
```

---

### Task 2: RRF fusion

**Files:**
- Create: `src/videosearch/search/rrf.py`
- Create: `tests/search/test_rrf.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/search/test_rrf.py
from videosearch.search.rrf import rrf_fuse


def test_single_list_preserves_order():
    result = rrf_fuse([["a", "b", "c"]])
    ids = [id_ for id_, _ in result]
    scores = [s for _, s in result]
    assert ids == ["a", "b", "c"]
    assert scores[0] > scores[1] > scores[2]


def test_item_in_both_lists_scores_higher():
    result = rrf_fuse([["a", "b"], ["b", "c"]])
    scores = {id_: s for id_, s in result}
    # "b" appears at rank 1 in list 0 and rank 0 in list 1 → highest combined score
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["c"]


def test_empty_input_returns_empty():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[]]) == []


def test_k_parameter_affects_score_magnitude():
    result_k1 = rrf_fuse([["a"]], k=1)
    result_k60 = rrf_fuse([["a"]], k=60)
    # k=1: 1/(1+0+1)=0.5; k=60: 1/(60+0+1)≈0.0164
    assert result_k1[0][1] > result_k60[0][1]


def test_returns_all_unique_ids():
    result = rrf_fuse([["a", "b"], ["b", "c", "d"]])
    ids = [id_ for id_, _ in result]
    assert set(ids) == {"a", "b", "c", "d"}
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/search/test_rrf.py -v
```

Expected: ERROR — `ModuleNotFoundError: No module named 'videosearch.search.rrf'`

- [ ] **Step 3: Implement RRF fusion**

```python
# src/videosearch/search/rrf.py
from __future__ import annotations


def rrf_fuse(ranked_lists: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    """Merge N ranked ID lists using Reciprocal Rank Fusion: score(d) = Σ 1/(k+rank+1)."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, id_ in enumerate(ranked):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/search/test_rrf.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/search/rrf.py tests/search/test_rrf.py
git commit -m "feat(search): add RRF fusion function"
```

---

### Task 3: Storage vector search methods

**Files:**
- Modify: `src/videosearch/storage/frame_embeddings.py`
- Modify: `src/videosearch/storage/caption_embeddings.py`
- Modify: `tests/storage/test_frame_embeddings.py`
- Modify: `tests/storage/test_caption_embeddings.py`

The existing `_frame` helper in `test_frame_embeddings.py` sets `timestamp_sec=float(idx)` — frame 0 → 0.0, frame 1 → 1.0, etc.

LanceDB vector search via `.search(vector).limit(k).to_list()` returns rows with an extra `_distance` key that must be stripped before constructing the Pydantic model.

- [ ] **Step 1: Write the failing tests**

Append to `tests/storage/test_frame_embeddings.py`:

```python
def test_search_returns_limited_rows(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_frame("v1", i) for i in range(5)])
    query = [0.1] * SIGLIP_DIM
    results = repo.search(query, limit=3)
    assert len(results) == 3
    assert all(isinstance(r, FrameEmbeddingRow) for r in results)


def test_find_nearest_returns_closest_by_timestamp(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_frame("v1", i) for i in range(5)])  # timestamps 0.0 .. 4.0
    result = repo.find_nearest("v1", 2.1)
    assert result is not None
    assert result.timestamp_sec == 2.0  # frame_idx=2


def test_find_nearest_returns_none_for_missing_video(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    assert repo.find_nearest("nonexistent", 0.0) is None
```

Append to `tests/storage/test_caption_embeddings.py`:

```python
def test_search_returns_limited_rows(tmp_path: Path):
    repo = CaptionEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_caption("v1", i) for i in range(5)])
    query = [0.2] * TEXT_EMBED_DIM
    results = repo.search(query, limit=3)
    assert len(results) == 3
    assert all(isinstance(r, CaptionEmbeddingRow) for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/storage/test_frame_embeddings.py tests/storage/test_caption_embeddings.py -v
```

Expected: 3 FAILED — `AttributeError: 'FrameEmbeddingsRepo' object has no attribute 'search'`

- [ ] **Step 3: Add search and find_nearest to FrameEmbeddingsRepo**

Replace the full content of `src/videosearch/storage/frame_embeddings.py`:

```python
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

    def search(self, query_vector: list[float], limit: int) -> list[FrameEmbeddingRow]:
        results = self._table.search(query_vector).limit(limit).to_list()
        return [FrameEmbeddingRow(**{k: v for k, v in r.items() if not k.startswith("_")}) for r in results]

    def find_nearest(self, video_id: str, timestamp_sec: float) -> FrameEmbeddingRow | None:
        rows = self.list_for_video(video_id)
        if not rows:
            return None
        return min(rows, key=lambda r: abs(r.timestamp_sec - timestamp_sec))

    def delete_for_video(self, video_id: str) -> None:
        self._table.delete(f"video_id = {_sql_literal(video_id)}")
```

Replace the full content of `src/videosearch/storage/caption_embeddings.py`:

```python
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

    def search(self, query_vector: list[float], limit: int) -> list[CaptionEmbeddingRow]:
        results = self._table.search(query_vector).limit(limit).to_list()
        return [CaptionEmbeddingRow(**{k: v for k, v in r.items() if not k.startswith("_")}) for r in results]

    def delete_for_video(self, video_id: str) -> None:
        self._table.delete(f"video_id = {_sql_literal(video_id)}")
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/storage/test_frame_embeddings.py tests/storage/test_caption_embeddings.py -v
```

Expected: 6 PASSED (3 existing + 3 new)

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/storage/frame_embeddings.py src/videosearch/storage/caption_embeddings.py \
        tests/storage/test_frame_embeddings.py tests/storage/test_caption_embeddings.py
git commit -m "feat(storage): add vector search and find_nearest to embedding repos"
```

---

### Task 4: Searcher class

**Files:**
- Create: `src/videosearch/search/searcher.py`
- Modify: `src/videosearch/search/__init__.py` — add Searcher to exports
- Create: `tests/search/test_searcher.py`

**How Searcher.search() works:**
1. Embed query with `image_embedder.embed_text(query)` → `frame_vec: list[float]`
2. Embed query with `text_embedder.embed_text([query])[0]` → `caption_vec: list[float]`
3. ANN search: `frames.search(frame_vec, limit=k*5)`, `captions.search(caption_vec, limit=k*5)`
4. Build composite ID dicts: `f:{video_id}:{frame_idx}` → row, `c:{video_id}:{scene_idx}` → row
5. RRF fuse ranked lists, iterate fused results to build `Moment` objects grouped by `video_id`
6. For caption hits: call `frames.find_nearest(video_id, row.start_sec)` to get `thumb_path`
7. Build `VideoResult` per video (sorted moments by score desc), sort results by `top_score` desc, return `SearchResponse`

- [ ] **Step 1: Write the failing tests**

```python
# tests/search/test_searcher.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from videosearch.search.models import SearchResponse
from videosearch.search.searcher import Searcher
from videosearch.storage.schemas import (
    SIGLIP_DIM,
    TEXT_EMBED_DIM,
    CaptionEmbeddingRow,
    FrameEmbeddingRow,
)


def _frame_row(video_id: str, frame_idx: int, ts: float) -> FrameEmbeddingRow:
    return FrameEmbeddingRow(
        video_id=video_id,
        frame_idx=frame_idx,
        timestamp_sec=ts,
        embedding=[0.1] * SIGLIP_DIM,
        thumb_path=f"/tmp/{video_id}_{frame_idx}.jpg",
    )


def _caption_row(video_id: str, scene_idx: int) -> CaptionEmbeddingRow:
    return CaptionEmbeddingRow(
        video_id=video_id,
        scene_idx=scene_idx,
        start_sec=0.0,
        end_sec=5.0,
        caption="a scene",
        embedding=[0.1] * TEXT_EMBED_DIM,
    )


def _make_searcher(
    frame_hits: list[FrameEmbeddingRow],
    caption_hits: list[CaptionEmbeddingRow],
    nearest: FrameEmbeddingRow | None = None,
) -> Searcher:
    frames = MagicMock()
    captions = MagicMock()
    image_emb = MagicMock()
    text_emb = MagicMock()

    image_emb.embed_text.return_value = [0.1] * SIGLIP_DIM
    text_emb.embed_text.return_value = [[0.1] * TEXT_EMBED_DIM]
    frames.search.return_value = frame_hits
    captions.search.return_value = caption_hits
    frames.find_nearest.return_value = nearest

    return Searcher(frames=frames, captions=captions, image_embedder=image_emb, text_embedder=text_emb)


def test_search_returns_search_response():
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 0, 1.0)],
        caption_hits=[],
    )
    result = searcher.search("test query")
    assert isinstance(result, SearchResponse)
    assert result.query == "test query"


def test_search_groups_moments_by_video():
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 0, 1.0), _frame_row("v2", 0, 1.0)],
        caption_hits=[],
    )
    result = searcher.search("test")
    assert len(result.results) == 2
    video_ids = {r.video_id for r in result.results}
    assert video_ids == {"v1", "v2"}


def test_search_returns_empty_for_no_hits():
    searcher = _make_searcher(frame_hits=[], caption_hits=[])
    result = searcher.search("nothing")
    assert result.results == []


def test_caption_hit_calls_find_nearest():
    nearest = _frame_row("v1", 0, 0.5)
    searcher = _make_searcher(
        frame_hits=[],
        caption_hits=[_caption_row("v1", 0)],
        nearest=nearest,
    )
    result = searcher.search("scene query")
    assert len(result.results) == 1
    moment = result.results[0].moments[0]
    assert moment.caption == "a scene"
    assert moment.thumb_path == nearest.thumb_path


def test_results_sorted_by_top_score_descending():
    # v1 appears in both frame and caption hits (higher RRF score)
    # v2 appears only in frame hits
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 0, 1.0), _frame_row("v2", 0, 1.0)],
        caption_hits=[_caption_row("v1", 0)],
        nearest=_frame_row("v1", 0, 0.5),
    )
    result = searcher.search("query")
    assert result.results[0].video_id == "v1"
    assert result.results[0].top_score >= result.results[1].top_score
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/search/test_searcher.py -v
```

Expected: ERROR — `ModuleNotFoundError: No module named 'videosearch.search.searcher'`

- [ ] **Step 3: Implement Searcher**

```python
# src/videosearch/search/searcher.py
from __future__ import annotations

from videosearch.models.protocols import ImageEmbedder, TextEmbedder
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo

from .models import Moment, SearchResponse, VideoResult
from .rrf import rrf_fuse


class Searcher:
    def __init__(
        self,
        *,
        frames: FrameEmbeddingsRepo,
        captions: CaptionEmbeddingsRepo,
        image_embedder: ImageEmbedder,
        text_embedder: TextEmbedder,
    ) -> None:
        self._frames = frames
        self._captions = captions
        self._image_embedder = image_embedder
        self._text_embedder = text_embedder

    def search(self, query: str, *, k: int = 10) -> SearchResponse:
        frame_vec = self._image_embedder.embed_text(query)
        caption_vec = self._text_embedder.embed_text([query])[0]

        frame_hits = self._frames.search(frame_vec, limit=k * 5)
        caption_hits = self._captions.search(caption_vec, limit=k * 5)

        frame_by_id = {f"f:{r.video_id}:{r.frame_idx}": r for r in frame_hits}
        caption_by_id = {f"c:{r.video_id}:{r.scene_idx}": r for r in caption_hits}

        fused = rrf_fuse([list(frame_by_id), list(caption_by_id)])

        moments_by_video: dict[str, list[Moment]] = {}
        for composite_id, score in fused:
            if composite_id.startswith("f:"):
                row = frame_by_id[composite_id]
                video_id = row.video_id
                moment = Moment(
                    timestamp_sec=row.timestamp_sec,
                    score=score,
                    thumb_path=row.thumb_path,
                )
            else:
                row = caption_by_id[composite_id]
                video_id = row.video_id
                nearest = self._frames.find_nearest(video_id, row.start_sec)
                moment = Moment(
                    timestamp_sec=row.start_sec,
                    score=score,
                    thumb_path=nearest.thumb_path if nearest else None,
                    caption=row.caption,
                )
            moments_by_video.setdefault(video_id, []).append(moment)

        results: list[VideoResult] = []
        for video_id, moments in moments_by_video.items():
            moments_sorted = sorted(moments, key=lambda m: m.score, reverse=True)
            results.append(VideoResult(
                video_id=video_id,
                top_score=moments_sorted[0].score,
                moments=moments_sorted,
            ))

        results.sort(key=lambda r: r.top_score, reverse=True)
        return SearchResponse(query=query, results=results[:k])
```

Update `src/videosearch/search/__init__.py` to include Searcher:

```python
# src/videosearch/search/__init__.py
from .models import Moment, SearchResponse, VideoResult
from .searcher import Searcher

__all__ = ["Moment", "SearchResponse", "Searcher", "VideoResult"]
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/search/test_searcher.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Run full test suite to check nothing regressed**

```
uv run pytest -v
```

Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add src/videosearch/search/searcher.py src/videosearch/search/__init__.py tests/search/test_searcher.py
git commit -m "feat(search): add Searcher class with RRF fusion over frames and captions"
```

---

### Task 5: Integration test

**Files:**
- Create: `tests/search/test_search_integration.py`

This test uses real LanceDB (in `tmp_path`), stub models, and `tiny.mp4` to verify the full search pipeline end-to-end. No mocks — real data, real embeddings, real storage.

- [ ] **Step 1: Write the integration test**

```python
# tests/search/test_search_integration.py
from pathlib import Path

from videosearch.indexer import index_video
from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.search.models import SearchResponse
from videosearch.search.searcher import Searcher
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.videos import VideosRepo


def test_search_finds_indexed_video(tmp_path: Path, tiny_video: Path):
    db = Database(tmp_path / "data")
    videos = VideosRepo(db)
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    image_embedder = StubImageEmbedder()
    text_embedder = StubTextEmbedder()
    captioner = StubCaptioner()

    result = index_video(
        path=tiny_video,
        videos=videos,
        frames=frames,
        captions=captions,
        image_embedder=image_embedder,
        text_embedder=text_embedder,
        captioner=captioner,
        work_dir=tmp_path / "work",
        frame_fps=2.0,
    )
    assert result.status == "indexed"

    searcher = Searcher(
        frames=frames,
        captions=captions,
        image_embedder=image_embedder,
        text_embedder=text_embedder,
    )
    response = searcher.search("a test query")

    assert isinstance(response, SearchResponse)
    assert response.query == "a test query"
    assert len(response.results) == 1
    assert response.results[0].video_id == result.video_id
    assert len(response.results[0].moments) >= 1
    assert response.results[0].top_score > 0.0


def test_search_returns_moments_with_timestamps(tmp_path: Path, tiny_video: Path):
    db = Database(tmp_path / "data")
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    index_video(
        path=tiny_video,
        videos=VideosRepo(db),
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
        captioner=StubCaptioner(),
        work_dir=tmp_path / "work",
        frame_fps=2.0,
    )

    searcher = Searcher(
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
    )
    response = searcher.search("query")

    for video_result in response.results:
        for moment in video_result.moments:
            assert moment.timestamp_sec >= 0.0
            assert moment.score > 0.0


def test_search_empty_db_returns_empty(tmp_path: Path):
    db = Database(tmp_path / "data")
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    searcher = Searcher(
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
    )
    response = searcher.search("anything")
    assert response.results == []
```

- [ ] **Step 2: Run the integration tests**

```
uv run pytest tests/search/test_search_integration.py -v
```

Expected: 3 PASSED

- [ ] **Step 3: Run the full test suite**

```
uv run pytest -v
```

Expected: all PASSED (no regressions)

- [ ] **Step 4: Commit**

```bash
git add tests/search/test_search_integration.py
git commit -m "test(search): add end-to-end integration tests for Searcher"
```

---

## Self-Review

**Spec coverage:**
- ✅ `expand_query` — treated as identity (query passed directly to embedders; no separate function needed until a real expansion strategy is chosen — YAGNI)
- ✅ RRF fusion — `rrf_fuse` in Task 2
- ✅ `Moment`, `VideoResult`, `SearchResponse` — Task 1
- ✅ ANN vector search on both repos — Task 3
- ✅ `Searcher` integrating everything — Task 4
- ✅ Integration test — Task 5

**Placeholder scan:** No TBDs, TODOs, or vague requirements.

**Type consistency:**
- `FrameEmbeddingsRepo.search(query_vector: list[float], limit: int) -> list[FrameEmbeddingRow]` — consistent across Task 3, 4, 5
- `CaptionEmbeddingsRepo.search(query_vector: list[float], limit: int) -> list[CaptionEmbeddingRow]` — consistent
- `FrameEmbeddingsRepo.find_nearest(video_id: str, timestamp_sec: float) -> FrameEmbeddingRow | None` — consistent
- `rrf_fuse(ranked_lists: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]` — consistent
- `Searcher.search(query: str, *, k: int = 10) -> SearchResponse` — consistent
- `Moment(timestamp_sec, score, thumb_path, caption=None)` — consistent across all tasks
