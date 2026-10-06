"""文本向量化：本地 sentence-transformers 或 OpenAI 兼容 `/embeddings`。

本地模型（默认 `BAAI/bge-small-zh-v1.5`）为阻塞任务，须在 worker 线程内调用。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from langchain_core.embeddings import Embeddings


class Embedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        provider: str = "local",
        base_url: str = "",
        api_key: str = "",
        model: Any = None,
    ) -> None:
        self.model_name = model_name
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._model = model  # 可注入，便于测试

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # 延迟导入

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """计算向量。`provider=api` 时内部走异步 `/embeddings`。"""
        if not texts:
            return []
        if self.provider == "api":
            return asyncio.run(self._embed_api(texts))
        return self._embed_local(texts)

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vectors]

    async def _embed_api(self, texts: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model_name, "input": texts},
            )
            resp.raise_for_status()
            payload = resp.json()
        return [list(item["embedding"]) for item in payload["data"]]


class LangChainEmbedding(Embeddings):
    """把项目一 `Embedder` 包成 LangChain `Embeddings` 适配器。

    委托现有 `Embedder.embed`，保证模型与归一化与存量向量一致，
    存量向量无需重建索引。
    """

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embedder.embed([text])[0]
