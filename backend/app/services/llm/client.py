"""OpenAI 兼容的 LLM 客户端（chat/completions，支持流式）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "",
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._timeout = timeout
        self._client = client

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout), headers=headers)
        return self._client

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _payload(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        stream: bool,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        return payload

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        resp = await self._http().post(
            self.endpoint, json=self._payload(messages, model, temperature, False, max_tokens)
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def complete_message(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> dict[str, Any]:
        """非流式调用，返回完整 assistant message（含可能的 `tool_calls`）。"""
        resp = await self._http().post(
            self.endpoint,
            json=self._payload(messages, model, temperature, False, None, tools, tool_choice),
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        async with self._http().stream(
            "POST", self.endpoint, json=self._payload(messages, model, temperature, True)
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:") :].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    obj = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield piece
