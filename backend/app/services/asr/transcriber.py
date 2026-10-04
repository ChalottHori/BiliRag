"""faster-whisper 转写封装（阻塞，调用方须放入线程池）。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MODEL_SIZES = ("small", "medium", "large-v3")


def _default_device() -> str:
    try:
        import torch  # 延迟导入，避免强依赖

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class WhisperTranscriber:
    def __init__(
        self,
        model_size: str = "medium",
        device: str | None = None,
        compute_type: str = "int8",
        model: Any = None,
    ) -> None:
        self.model_size = model_size
        self.device = device or _default_device()
        self.compute_type = compute_type
        self._model = model  # 可注入，便于测试

    def _ensure_model(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel  # 延迟导入

            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def transcribe(self, audio_path: str) -> str:
        """转写音频为全文稿（阻塞；返回拼接后的纯文本）。"""
        model = self._ensure_model()
        segments, _info = model.transcribe(audio_path, beam_size=5)
        return "".join(seg.text for seg in segments)
