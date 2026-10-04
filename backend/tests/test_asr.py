"""ASR 转写封装单测（mock 模型，离线）。"""

from __future__ import annotations

import builtins
from typing import Any

from app.services.asr.transcriber import WhisperTranscriber, _default_device


class _FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModel:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts

    def transcribe(
        self, path: str, beam_size: int = 5
    ) -> tuple[list[_FakeSegment], dict[str, Any]]:
        return [_FakeSegment(t) for t in self._texts], {}


def test_transcribe_concatenates() -> None:
    transcriber = WhisperTranscriber(model_size="small", model=_FakeModel(["你", "好", "世界"]))
    assert transcriber.transcribe("audio.m4s") == "你好世界"


def test_default_device_falls_back_to_cpu(monkeypatch: Any) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "torch":
            raise ImportError("torch not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert _default_device() == "cpu"
