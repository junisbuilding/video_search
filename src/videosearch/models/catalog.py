from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelEntry:
    id: str
    label: str
    size_label: str
    hf_repo: str | None       # HuggingFace repo ID — for SigLIP and text embedder
    vlm_model: str | None     # repo_id::filename — for vision GGUF model file only
    vlm_mmproj: str | None    # repo_id::filename — for vision GGUF mmproj file only
    default: bool = False


CATALOG: dict[str, tuple[ModelEntry, ...]] = {
    "vision": (
        ModelEntry(
            id="moondream2",
            label="moondream2",
            size_label="~2 GB",
            hf_repo=None,
            vlm_model="moondream/moondream2-gguf::moondream2-text-model-f16.gguf",
            vlm_mmproj="moondream/moondream2-gguf::moondream2-mmproj-f16.gguf",
            default=True,
        ),
        ModelEntry(
            id="llava-1.5-7b",
            label="LLaVA 1.5 · 7B",
            size_label="~4 GB",
            hf_repo=None,
            vlm_model="mys/ggml_llava-v1.5-7b::ggml-model-q4_k.gguf",
            vlm_mmproj="mys/ggml_llava-v1.5-7b::mmproj-model-f16.gguf",
        ),
        ModelEntry(
            id="llava-1.5-13b",
            label="LLaVA 1.5 · 13B",
            size_label="~8 GB",
            hf_repo=None,
            vlm_model="mys/ggml_llava-v1.5-13b::ggml-model-q4_k.gguf",
            vlm_mmproj="mys/ggml_llava-v1.5-13b::mmproj-model-f16.gguf",
        ),
    ),
    "siglip": (
        ModelEntry(
            id="siglip2-base",
            label="SigLIP Base",
            size_label="~1.2 GB",
            hf_repo="google/siglip2-base-patch16-256",
            vlm_model=None,
            vlm_mmproj=None,
            default=True,
        ),
        ModelEntry(
            id="siglip2-large",
            label="SigLIP Large",
            size_label="~3.5 GB",
            hf_repo="google/siglip2-large-patch16-256",
            vlm_model=None,
            vlm_mmproj=None,
        ),
        ModelEntry(
            id="siglip-so400m",
            label="SigLIP SO400M",
            size_label="~1.6 GB",
            hf_repo="google/siglip-so400m-patch14-384",
            vlm_model=None,
            vlm_mmproj=None,
        ),
    ),
    "text_embedder": (
        ModelEntry(
            id="bge-small-en",
            label="BGE Small (English)",
            size_label="~130 MB",
            hf_repo="BAAI/bge-small-en-v1.5",
            vlm_model=None,
            vlm_mmproj=None,
            default=True,
        ),
        ModelEntry(
            id="bge-base-en",
            label="BGE Base (English)",
            size_label="~430 MB",
            hf_repo="BAAI/bge-base-en-v1.5",
            vlm_model=None,
            vlm_mmproj=None,
        ),
        ModelEntry(
            id="bge-large-en",
            label="BGE Large (English)",
            size_label="~1.3 GB",
            hf_repo="BAAI/bge-large-en-v1.5",
            vlm_model=None,
            vlm_mmproj=None,
        ),
        ModelEntry(
            id="bge-m3",
            label="BGE M3 (multilingual)",
            size_label="~2 GB",
            hf_repo="BAAI/bge-m3",
            vlm_model=None,
            vlm_mmproj=None,
        ),
    ),
}


def find_by_id(model_type: str, model_id: str) -> ModelEntry | None:
    """Return the entry with the given id, or None if not found (including unknown type)."""
    for entry in CATALOG.get(model_type, ()):
        if entry.id == model_id:
            return entry
    return None


def get_default(model_type: str) -> ModelEntry:
    """Return the default entry for a model type. Raises KeyError for unknown type."""
    entries = CATALOG[model_type]  # raises KeyError for unknown type — intentional per spec
    for entry in entries:
        if entry.default:
            return entry
    raise ValueError(f"No default entry configured for model type '{model_type}'")
