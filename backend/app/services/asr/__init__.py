"""ASR 服务：faster-whisper 封装。"""

from __future__ import annotations

from .transcriber import MODEL_SIZES, WhisperTranscriber

__all__ = ["MODEL_SIZES", "WhisperTranscriber"]
