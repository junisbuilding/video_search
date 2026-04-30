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
