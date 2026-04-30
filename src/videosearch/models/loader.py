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
