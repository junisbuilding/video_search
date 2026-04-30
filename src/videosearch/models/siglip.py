from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

from videosearch.models._device import select_device


class SiglipEmbedder:
    def __init__(self, model_name: str, *, device: str | None = None):
        self.device = select_device(device)
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
