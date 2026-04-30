from __future__ import annotations

import torch


def select_device(device: str | None) -> str:
    """Return the best available device: MPS (Mac) → CUDA (Linux/NVIDIA) → CPU."""
    if device is not None:
        return device
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"
