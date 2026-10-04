"""LLM 客户端与摘要单测（mock 网络，离线）。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx

from app.services.llm.client import LLMClient
from app.services.llm.summarize import chunk_text, parse_summary, summarize


# ------------------------------------------------------------------ 纯逻辑
def test_parse_summary_json() -> None:
    text = '{"title": "标题", "overview": "概述", "points": ["a", "b"], "keywords": ["k"]}'
    result = parse_summary(text)
    assert result["title"] == "标题"
    assert result["overview"] == "概述"
    assert result["points"] == ["a", "b"]
    assert result["keywords"] == ["k"]


def test_parse_summary_fenced() -> None:
    text = '```json\n{"title": "t", "overview": "o", "points": [], "keywords": []}\n```'
    assert parse_summary(text)["title"] == "t"


def test_parse_summary_fallback() -> None:
    result = parse_summary("这不是 JSON")
    assert result["overview"] == "这不是 JSON"
    assert result["points"] == []
    assert result["title"] == ""


def test_chunk_text() -> None:
    assert chunk_text("") == []
    assert chunk_text("hello", chunk_size=100) == ["hello"]
    assert chunk_text("abcdefghij", chunk_size=4, overlap=2) == [
        "abcd",
        "cdef",
        "efgh",
        "ghij",
        "ij",
    ]


# ------------------------------------------------------------------ 摘要（mock LLM）
class _FakeSummaryClient:
    async def complete(
        self, messages: list[dict[str, str]], model: str | None = None, **kw: Any
    ) -> str:
        return '{"title": "t", "overview": "o", "points": ["p"], "keywords": ["k"]}'


def test_summarize_short() -> None:
    result = asyncio.run(summarize("短文内容", _FakeSummaryClient()))
    assert result["title"] == "t"


def test_summarize_long_map_reduce() -> None:
    calls: list[str] = []

    class FakeClient:
        async def complete(
            self, messages: list[dict[str, str]], model: str | None = None, **kw: Any
        ) -> str:
            content = messages[-1]["content"]
            calls.append(content)
            if content.startswith("【片段"):
                return '{"title": "合并", "overview": "概述", "points": ["x"], "keywords": []}'
            return '{"title": "分块", "overview": "o", "points": [], "keywords": []}'

    transcript = "x" * 5000
    result = asyncio.run(summarize(transcript, FakeClient(), chunk_size=1000, overlap=0))
    assert result["title"] == "合并"
    # 5 次 map + 1 次 reduce
    assert len(calls) == 6


# ------------------------------------------------------------------ 客户端（mock transport）
def _llm_client(handler: Callable[[httpx.Request], httpx.Response]) -> LLMClient:
    return LLMClient(
        base_url="http://mock/v1",
        api_key="k",
        model="m",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def test_complete_non_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    out = asyncio.run(_llm_client(handler).complete([{"role": "user", "content": "q"}]))
    assert out == "hi"


def test_stream_complete() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
            "data: [DONE]\n\n"
        ).encode()
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    async def run() -> list[str]:
        pieces: list[str] = []
        async for piece in _llm_client(handler).stream_complete([{"role": "user", "content": "q"}]):
            pieces.append(piece)
        return pieces

    assert asyncio.run(run()) == ["你", "好"]
