"""Chroma 向量库封装（langchain_chroma，单 collection `items`）。

一致性约定（Part 0.7 第 3 条）：
- 向量 id = `{item_id}:{chunk_idx}`；metadata 必带 `item_id`。
- collection 名 `items`、`hnsw:space=cosine` 与历史一致，存量向量继续有效。
- 删除条目用 `collection.delete(where={"item_id": ...})`。
- 重新总结先删后写（幂等）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from .embedder import Embedder, LangChainEmbedding

COLLECTION_NAME = "items"


def _sanitize(meta: dict[str, Any]) -> dict[str, Any]:
    """Chroma metadata 只接受标量，None 统一转空串。"""
    return {k: ("" if v is None else v) for k, v in meta.items()}


class VectorStore:
    def __init__(
        self,
        path: str | Path | None = None,
        embedder: Embedder | None = None,
        client: Any = None,
    ) -> None:
        self._path = str(path) if path else None
        self._embedder = embedder
        self._client = client  # 可注入，便于测试（如 EphemeralClient）
        self._vectorstore: Chroma | None = None

    def _get_store(self) -> Chroma:
        if self._vectorstore is None:
            # delete 不需要 embedding；无 embedder 时（如 api/items 删除条目）
            # 仍可构造 store，仅 add / search_mmr 会要求 embedder。
            embedding_function = (
                LangChainEmbedding(self._embedder) if self._embedder is not None else None
            )
            self._vectorstore = Chroma(
                collection_name=COLLECTION_NAME,
                collection_metadata={"hnsw:space": "cosine"},
                embedding_function=embedding_function,
                persist_directory=self._path,
                client=self._client,
            )
        return self._vectorstore

    def _require_embedder(self) -> None:
        if self._embedder is None:
            raise ValueError("VectorStore 需要 embedder（Embedder 实例）")

    def add(self, item_id: str, chunks: list[str], metadata: dict[str, Any]) -> int:
        """写入一个条目的所有分块，返回写入文档数（= len(chunks)）。"""
        self._require_embedder()
        if not chunks:
            return 0
        documents = [
            Document(
                page_content=chunk,
                metadata=_sanitize({**metadata, "item_id": item_id, "chunk_idx": idx}),
            )
            for idx, chunk in enumerate(chunks)
        ]
        ids = [f"{item_id}:{idx}" for idx in range(len(chunks))]
        self._get_store().add_documents(documents, ids=ids)
        return len(chunks)

    def delete(self, item_id: str) -> None:
        self._get_store().delete(where={"item_id": item_id})

    def search_mmr(
        self,
        query: str,
        k: int,
        fetch_k: int,
        lambda_mult: float,
        where: dict[str, Any] | None,
    ) -> list[Document]:
        """MMR 检索，返回 langchain `Document`；`where` 为 chroma filter dict。"""
        self._require_embedder()
        return self._get_store().max_marginal_relevance_search(
            query,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filter=where,
        )
