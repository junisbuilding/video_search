# Video Search Phase 2 — Real Model Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three real model adapters (`SiglipEmbedder`, `BgeTextEmbedder`, `LlamaCppCaptioner`) plus a GGUF downloader, satisfying the protocols defined in Phase 1.

**Architecture:** Each adapter lives in its own file under `src/videosearch/models/`, implements the matching Protocol from `protocols.py`, and auto-selects MPS (Mac) / CUDA (Linux) / CPU. A `loader.py` handles resolving `repo_id::filename` HF Hub specs to local GGUF paths. Unit tests mock the heavyweight libraries so the suite stays fast; real-model smoke tests are gated behind a `smoke` pytest marker and excluded from the normal run.

**Tech Stack:** `torch>=2.2`, `transformers>=4.40`, `accelerate>=0.27`, `sentence-transformers>=3.0`, `llama-cpp-python>=0.2.80`, `huggingface-hub>=0.22`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `pyproject.toml` | Modify | Add model dependencies and smoke marker |
| `src/videosearch/models/siglip.py` | Create | `SiglipEmbedder` — image + text encoder |
| `src/videosearch/models/bge.py` | Create | `BgeTextEmbedder` — caption text embedder |
| `src/videosearch/models/llama_cpp_captioner.py` | Create | `LlamaCppCaptioner` — VLM via llama-cpp-python |
| `src/videosearch/models/loader.py` | Create | `resolve_gguf()` — local path or HF download |
| `tests/models/test_imports.py` | Create | Verify all deps importable |
| `tests/models/test_siglip.py` | Create | Unit tests with mocked transformers |
| `tests/models/test_bge.py` | Create | Unit tests with mocked sentence-transformers |
| `tests/models/test_llama_cpp_captioner.py` | Create | Unit tests with mocked Llama |
| `tests/models/test_loader.py` | Create | Unit tests with mocked hf_hub_download |
| `tests/models/test_smoke.py` | Create | Real-model smoke tests (smoke marker) |

---

### Task 1: Add dependencies and smoke marker

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/models/test_imports.py`

- [ ] **Step 1: Write the failing import test**

```python
# tests/models/test_imports.py
def test_model_deps_importable():
    import torch  # noqa: F401
    import transformers  # noqa: F401
    import sentence_transformers  # noqa: F401
    import llama_cpp  # noqa: F401
    import huggingface_hub  # noqa: F401
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/models/test_imports.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Update `pyproject.toml`**

Replace the `dependencies` list and `[tool.pytest.ini_options]` section:

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
    "torch>=2.2",
    "transformers>=4.40",
    "accelerate>=0.27",
    "sentence-transformers>=3.0",
    "llama-cpp-python>=0.2.80",
    "huggingface-hub>=0.22",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1",
    "ruff>=0.4",
]
```

And update `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q -m 'not smoke'"
markers = [
    "smoke: load real model weights — run with: uv run pytest -m smoke",
]
```

- [ ] **Step 4: Install new dependencies**

```bash
uv sync --all-extras
```

- [ ] **Step 5: Run import test**

```bash
uv run pytest tests/models/test_imports.py -v
```
Expected: PASS

- [ ] **Step 6: Run full suite to check nothing broke**

```bash
uv run pytest tests/ -v
```
Expected: All prior tests pass (51 passed).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml tests/models/test_imports.py
git commit -m "feat: add torch/transformers/sentence-transformers/llama-cpp-python deps"
```

---

### Task 2: SiglipEmbedder

**Files:**
- Create: `src/videosearch/models/siglip.py`
- Create: `tests/models/test_siglip.py`

`SiglipEmbedder` wraps `google/siglip2-base-patch16-256` with `transformers`. `embed_images` L2-normalises and returns `list[list[float]]` of length `SIGLIP_DIM=768`. `embed_text` returns a single `list[float]` of the same dimension. Device is MPS → CUDA → CPU.

The test patches `AutoProcessor` and `AutoModel` at import time so no weights are downloaded. The key subtlety: the processor mock's return value must support `.to(device)` and `**`-unpacking (as a mapping). We achieve this with `MagicMock(spec=dict)` + `.to.return_value = self`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/models/test_siglip.py
import torch
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from videosearch.models.siglip import SiglipEmbedder
from videosearch.storage.schemas import SIGLIP_DIM


def _mock_inputs() -> MagicMock:
    """BatchEncoding stand-in: supports .to() and **-unpacking."""
    m = MagicMock(spec=dict)
    m.keys.return_value = []  # ** unpacking yields empty dict
    m.to.return_value = m
    return m


def _make_embedder() -> tuple[SiglipEmbedder, MagicMock, MagicMock]:
    mock_processor = MagicMock()
    mock_processor.return_value = _mock_inputs()

    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = mock_model
    mock_model.get_image_features.return_value = torch.randn(2, SIGLIP_DIM)
    mock_model.get_text_features.return_value = torch.randn(1, SIGLIP_DIM)

    with patch("videosearch.models.siglip.AutoProcessor") as MockProc, \
         patch("videosearch.models.siglip.AutoModel") as MockMod:
        MockProc.from_pretrained.return_value = mock_processor
        MockMod.from_pretrained.return_value = mock_model
        embedder = SiglipEmbedder("mock-model", device="cpu")

    return embedder, mock_processor, mock_model


def test_embed_images_returns_correct_shape(tmp_path: Path):
    img1 = tmp_path / "a.jpg"
    img2 = tmp_path / "b.jpg"
    Image.new("RGB", (32, 32)).save(img1)
    Image.new("RGB", (32, 32)).save(img2)

    embedder, _, mock_model = _make_embedder()
    mock_model.get_image_features.return_value = torch.randn(2, SIGLIP_DIM)

    result = embedder.embed_images([img1, img2])

    assert len(result) == 2
    assert len(result[0]) == SIGLIP_DIM
    assert len(result[1]) == SIGLIP_DIM


def test_embed_text_returns_correct_shape():
    embedder, _, mock_model = _make_embedder()
    mock_model.get_text_features.return_value = torch.randn(1, SIGLIP_DIM)

    result = embedder.embed_text("a cat on a roof")

    assert len(result) == SIGLIP_DIM
    assert isinstance(result[0], float)
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/models/test_siglip.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'videosearch.models.siglip'`

- [ ] **Step 3: Implement `src/videosearch/models/siglip.py`**

```python
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor


def _select_device(device: str | None) -> str:
    if device is not None:
        return device
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class SiglipEmbedder:
    def __init__(self, model_name: str, *, device: str | None = None):
        self.device = _select_device(device)
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()

    def embed_images(self, images: Sequence[Path]) -> list[list[float]]:
        pil_images = [Image.open(p).convert("RGB") for p in images]
        inputs = self.processor(images=pil_images, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            vecs = self.model.get_image_features(**inputs)
            vecs = vecs / vecs.norm(dim=-1, keepdim=True)
        return vecs.cpu().float().tolist()

    def embed_text(self, text: str) -> list[float]:
        inputs = self.processor(text=[text], return_tensors="pt", padding=True).to(self.device)
        with torch.inference_mode():
            vec = self.model.get_text_features(**inputs)
            vec = vec / vec.norm(dim=-1, keepdim=True)
        return vec.cpu().float().squeeze(0).tolist()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/models/test_siglip.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/models/siglip.py tests/models/test_siglip.py
git commit -m "feat: add SiglipEmbedder (image + text encoder, MPS/CUDA/CPU)"
```

---

### Task 3: BgeTextEmbedder

**Files:**
- Create: `src/videosearch/models/bge.py`
- Create: `tests/models/test_bge.py`

Wraps `BAAI/bge-small-en-v1.5` via `sentence-transformers`. Returns L2-normalised `TEXT_EMBED_DIM=384`-dim vectors for a batch of strings.

- [ ] **Step 1: Write the failing tests**

```python
# tests/models/test_bge.py
import numpy as np
from unittest.mock import MagicMock, patch

from videosearch.models.bge import BgeTextEmbedder
from videosearch.storage.schemas import TEXT_EMBED_DIM


def _make_embedder(n: int = 2) -> tuple[BgeTextEmbedder, MagicMock]:
    mock_st = MagicMock()
    mock_st.encode.return_value = np.random.randn(n, TEXT_EMBED_DIM).astype("float32")
    with patch("videosearch.models.bge.SentenceTransformer") as MockST:
        MockST.return_value = mock_st
        embedder = BgeTextEmbedder("mock-model")
    return embedder, mock_st


def test_embed_text_batch_shape():
    embedder, mock_st = _make_embedder(n=3)
    mock_st.encode.return_value = np.random.randn(3, TEXT_EMBED_DIM).astype("float32")

    result = embedder.embed_text(["hello", "world", "foo"])

    assert len(result) == 3
    assert len(result[0]) == TEXT_EMBED_DIM


def test_embed_text_single_shape():
    embedder, mock_st = _make_embedder(n=1)
    mock_st.encode.return_value = np.random.randn(1, TEXT_EMBED_DIM).astype("float32")

    result = embedder.embed_text(["hello"])

    assert len(result) == 1
    assert len(result[0]) == TEXT_EMBED_DIM


def test_embed_text_calls_encode_with_normalize():
    embedder, mock_st = _make_embedder(n=1)

    embedder.embed_text(["test"])

    mock_st.encode.assert_called_once()
    _, kwargs = mock_st.encode.call_args
    assert kwargs.get("normalize_embeddings") is True
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/models/test_bge.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'videosearch.models.bge'`

- [ ] **Step 3: Implement `src/videosearch/models/bge.py`**

```python
from __future__ import annotations

from collections.abc import Sequence

import torch
from sentence_transformers import SentenceTransformer


def _select_device(device: str | None) -> str:
    if device is not None:
        return device
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class BgeTextEmbedder:
    def __init__(self, model_name: str, *, device: str | None = None):
        self._model = SentenceTransformer(model_name, device=_select_device(device))

    def embed_text(self, texts: Sequence[str]) -> list[list[float]]:
        vecs = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vecs.tolist()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/models/test_bge.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/models/bge.py tests/models/test_bge.py
git commit -m "feat: add BgeTextEmbedder (sentence-transformers wrapper)"
```

---

### Task 4: LlamaCppCaptioner

**Files:**
- Create: `src/videosearch/models/llama_cpp_captioner.py`
- Create: `tests/models/test_llama_cpp_captioner.py`

Wraps Qwen2.5-VL GGUF via `llama-cpp-python`. Images are base64-encoded into `data:` URIs and passed as OpenAI-style chat content. `Qwen2VLChatHandler` loads the multimodal projector (mmproj).

Note: `Qwen2VLChatHandler` is available in `llama-cpp-python>=0.2.80`. Verify it exists with `python -c "from llama_cpp.llama_chat_format import Qwen2VLChatHandler"` after install. If the class name differs in your installed version, check `dir(llama_cpp.llama_chat_format)` for the correct name.

- [ ] **Step 1: Write the failing tests**

```python
# tests/models/test_llama_cpp_captioner.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from videosearch.models.llama_cpp_captioner import LlamaCppCaptioner


def _make_captioner(tmp_path: Path) -> tuple[LlamaCppCaptioner, MagicMock]:
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "A person walks through a door."}}]
    }
    with patch("videosearch.models.llama_cpp_captioner.Llama") as MockLlama, \
         patch("videosearch.models.llama_cpp_captioner.Qwen2VLChatHandler"):
        MockLlama.return_value = mock_llm
        captioner = LlamaCppCaptioner(
            model_path=str(tmp_path / "model.gguf"),
            mmproj_path=str(tmp_path / "mmproj.gguf"),
        )
    return captioner, mock_llm


def test_caption_returns_string(tmp_path: Path):
    img = tmp_path / "frame.jpg"
    Image.new("RGB", (64, 64)).save(img)

    captioner, _ = _make_captioner(tmp_path)
    result = captioner.caption([img], prompt="Describe this scene.")

    assert isinstance(result, str)
    assert len(result) > 0


def test_caption_calls_llm_once(tmp_path: Path):
    img = tmp_path / "frame.jpg"
    Image.new("RGB", (64, 64)).save(img)

    captioner, mock_llm = _make_captioner(tmp_path)
    captioner.caption([img], prompt="Describe this scene.")

    mock_llm.create_chat_completion.assert_called_once()


def test_caption_strips_whitespace(tmp_path: Path):
    img = tmp_path / "frame.jpg"
    Image.new("RGB", (64, 64)).save(img)

    captioner, mock_llm = _make_captioner(tmp_path)
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "  A cat.  \n"}}]
    }
    result = captioner.caption([img], prompt="Describe.")

    assert result == "A cat."
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/models/test_llama_cpp_captioner.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/videosearch/models/llama_cpp_captioner.py`**

```python
from __future__ import annotations

import base64
from collections.abc import Sequence
from pathlib import Path

from llama_cpp import Llama
from llama_cpp.llama_chat_format import Qwen2VLChatHandler

_MIME: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


def _to_data_uri(path: Path) -> str:
    mime = _MIME.get(path.suffix.lower().lstrip("."), "image/jpeg")
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


class LlamaCppCaptioner:
    def __init__(
        self,
        model_path: str,
        mmproj_path: str,
        *,
        n_gpu_layers: int = -1,
        n_ctx: int = 4096,
    ):
        handler = Qwen2VLChatHandler(clip_model_path=mmproj_path)
        self._llm = Llama(
            model_path=str(model_path),
            chat_handler=handler,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )

    def caption(self, images: Sequence[Path], *, prompt: str) -> str:
        content: list[dict] = [
            {"type": "image_url", "image_url": {"url": _to_data_uri(Path(p))}}
            for p in images
        ]
        content.append({"type": "text", "text": prompt})
        response = self._llm.create_chat_completion(
            messages=[{"role": "user", "content": content}],
            max_tokens=256,
            temperature=0.0,
        )
        return response["choices"][0]["message"]["content"].strip()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/models/test_llama_cpp_captioner.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/models/llama_cpp_captioner.py tests/models/test_llama_cpp_captioner.py
git commit -m "feat: add LlamaCppCaptioner (Qwen2.5-VL via llama-cpp-python)"
```

---

### Task 5: GGUF path resolver

**Files:**
- Create: `src/videosearch/models/loader.py`
- Create: `tests/models/test_loader.py`

`resolve_gguf(spec, cache_dir)` converts a model spec to a local `Path`. If `spec` contains `::`, it's treated as `repo_id::filename` and downloaded via `hf_hub_download`. Otherwise it must be a local path that already exists.

- [ ] **Step 1: Write the failing tests**

```python
# tests/models/test_loader.py
import pytest
from pathlib import Path
from unittest.mock import patch

from videosearch.models.loader import resolve_gguf


def test_resolve_local_path(tmp_path: Path):
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"fake")

    result = resolve_gguf(str(gguf), cache_dir=tmp_path)

    assert result == gguf


def test_resolve_hf_spec(tmp_path: Path):
    spec = "bartowski/Qwen2.5-VL-3B-Instruct-GGUF::Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
    fake_path = tmp_path / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
    fake_path.write_bytes(b"fake")

    with patch("videosearch.models.loader.hf_hub_download", return_value=str(fake_path)) as mock_dl:
        result = resolve_gguf(spec, cache_dir=tmp_path)

    mock_dl.assert_called_once_with(
        "bartowski/Qwen2.5-VL-3B-Instruct-GGUF",
        "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
        cache_dir=str(tmp_path),
    )
    assert result == fake_path


def test_resolve_missing_local_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_gguf(str(tmp_path / "nonexistent.gguf"), cache_dir=tmp_path)
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/models/test_loader.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'videosearch.models.loader'`

- [ ] **Step 3: Implement `src/videosearch/models/loader.py`**

```python
from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download

_HF_SEP = "::"


def resolve_gguf(spec: str, *, cache_dir: Path) -> Path:
    """Resolve a GGUF spec to a local path.

    spec is either a local file path or "repo_id::filename" for HF Hub.
    """
    if _HF_SEP in spec:
        repo_id, filename = spec.split(_HF_SEP, 1)
        local = hf_hub_download(repo_id, filename, cache_dir=str(cache_dir))
        return Path(local)

    path = Path(spec)
    if not path.exists():
        raise FileNotFoundError(f"GGUF file not found: {path}")
    return path
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/models/test_loader.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/models/loader.py tests/models/test_loader.py
git commit -m "feat: add resolve_gguf (local path or HF Hub download)"
```

---

### Task 6: Smoke tests for real model inference

**Files:**
- Create: `tests/models/test_smoke.py`

Smoke tests run the full model load + inference chain with real weights. They're excluded from the normal suite by the `-m 'not smoke'` addopts set in Task 1. Run them manually:

```bash
uv run pytest -m smoke -v
```

Prerequisites:
- Models downloaded (or accessible via HF Hub with internet).
- For the VLM test: set `VS_VLM_MODEL` and `VS_VLM_MMPROJ` env vars.
- Example:
  ```
  VS_VLM_MODEL=bartowski/Qwen2.5-VL-3B-Instruct-GGUF::Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf
  VS_VLM_MMPROJ=bartowski/Qwen2.5-VL-3B-Instruct-GGUF::Qwen2.5-VL-3B-Instruct-mmproj-f16.gguf
  ```

- [ ] **Step 1: Write the smoke tests**

```python
# tests/models/test_smoke.py
"""
Real-model smoke tests. Run with: uv run pytest -m smoke -v

SigLIP and BGE download from HF Hub automatically on first run (~750 MB total).
VLM requires VS_VLM_MODEL and VS_VLM_MMPROJ to be set (see plan header).
"""
import pytest
from pathlib import Path
from PIL import Image

from videosearch.config import load_config
from videosearch.models.loader import resolve_gguf
from videosearch.models.siglip import SiglipEmbedder
from videosearch.models.bge import BgeTextEmbedder
from videosearch.models.llama_cpp_captioner import LlamaCppCaptioner
from videosearch.storage.schemas import SIGLIP_DIM, TEXT_EMBED_DIM


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def test_image(tmp_path_factory) -> Path:
    img = tmp_path_factory.mktemp("smoke") / "frame.jpg"
    Image.new("RGB", (256, 256), color=(100, 149, 237)).save(img)
    return img


@pytest.mark.smoke
def test_siglip_image_embedding_shape(cfg, test_image):
    embedder = SiglipEmbedder(cfg.siglip_model)
    vecs = embedder.embed_images([test_image])

    assert len(vecs) == 1
    assert len(vecs[0]) == SIGLIP_DIM


@pytest.mark.smoke
def test_siglip_text_embedding_shape(cfg):
    embedder = SiglipEmbedder(cfg.siglip_model)
    vec = embedder.embed_text("a colorful abstract image")

    assert len(vec) == SIGLIP_DIM


@pytest.mark.smoke
def test_bge_embedding_shape(cfg):
    embedder = BgeTextEmbedder(cfg.text_embedder)
    vecs = embedder.embed_text(["hello world", "second sentence"])

    assert len(vecs) == 2
    assert len(vecs[0]) == TEXT_EMBED_DIM


@pytest.mark.smoke
def test_llama_cpp_captioner(cfg, test_image):
    if not cfg.vlm_model or not cfg.vlm_mmproj:
        pytest.skip("VS_VLM_MODEL and VS_VLM_MMPROJ not set")

    model_path = resolve_gguf(cfg.vlm_model, cache_dir=cfg.models_dir)
    mmproj_path = resolve_gguf(cfg.vlm_mmproj, cache_dir=cfg.models_dir)

    captioner = LlamaCppCaptioner(str(model_path), str(mmproj_path))
    result = captioner.caption(
        [test_image],
        prompt="Describe this image in one sentence.",
    )

    assert isinstance(result, str)
    assert len(result) > 5
```

- [ ] **Step 2: Run normal suite — verify smoke tests are excluded**

```bash
uv run pytest tests/ -v
```
Expected: All prior non-smoke tests pass. `test_smoke.py` tests are deselected.

- [ ] **Step 3: Commit**

```bash
git add tests/models/test_smoke.py
git commit -m "test: add smoke tests for real model inference (excluded from normal run)"
```

---

## Self-Review

**Spec coverage:**
- SigLIP 2 image + text encoder → Task 2 ✓
- bge-small text embedder → Task 3 ✓
- Qwen2.5-VL via llama-cpp-python → Task 4 ✓
- Model download / HF Hub resolution → Task 5 ✓
- Device auto-selection MPS/CUDA/CPU → Tasks 2, 3, 4 ✓
- Smoke test with real models → Task 6 ✓
- Protocol compliance (`ImageEmbedder`, `TextEmbedder`, `Captioner`) → each adapter satisfies its protocol by construction ✓

**Protocol signatures matched:**
- `SiglipEmbedder.embed_images(Sequence[Path]) -> list[list[float]]` ✓
- `SiglipEmbedder.embed_text(str) -> list[float]` ✓
- `BgeTextEmbedder.embed_text(Sequence[str]) -> list[list[float]]` ✓
- `LlamaCppCaptioner.caption(Sequence[Path], *, prompt: str) -> str` ✓

**Type consistency across tasks:**
- `resolve_gguf(spec: str, *, cache_dir: Path) -> Path` — same signature in Task 5 implementation and Task 6 smoke test ✓
- `SiglipEmbedder(model_name, *, device)` — consistent Tasks 2 and 6 ✓
- `LlamaCppCaptioner(model_path, mmproj_path, *, n_gpu_layers, n_ctx)` — consistent Tasks 4 and 6 ✓

**No placeholders:** All code blocks are complete and runnable.
