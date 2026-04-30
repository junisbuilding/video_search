from __future__ import annotations

import base64
from collections.abc import Sequence
from pathlib import Path

from llama_cpp import Llama
from llama_cpp.llama_chat_format import Qwen25VLChatHandler as Qwen2VLChatHandler

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
        content: list[dict[str, object]] = [
            {"type": "image_url", "image_url": {"url": _to_data_uri(p)}}
            for p in images
        ]
        content.append({"type": "text", "text": prompt})
        response = self._llm.create_chat_completion(
            messages=[{"role": "user", "content": content}],
            max_tokens=256,
            temperature=0.0,
        )
        return response["choices"][0]["message"]["content"].strip()
