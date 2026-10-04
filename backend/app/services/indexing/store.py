"""Chroma 向量库封装（单 collection `items`）。

一致性约定（Part 0.7 第 3 条）：
- 向量 id = `{item_id}:{chunk_idx}`；metadata 必带 `item_id`。
- 删除条目用 `collection.delete(where={"item_id": ...})`。
- 重新总结先删后写（幂等）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

COLLECTION_NAME = "items"


def _sanitize(meta: dict[str, Any]) -> dict[str, Any]:
    """Chroma metadata 只接受标量，None 统一转空串。"""
    return {k: ("" if v is None else v) for k, v in meta.items()}


class VectorStore:
    def __init__(
        self,
        path: str | Path | None = None,
        client: Any = None,
        collection: Any = None,
    ) -> None:
        self._path = path
        self._client = client  # 可注入，便于测试
        self._collection = collection  # 可注入，便于测试

    def _get_client(self) -> Any:
        if self._client is None:
            import chromadb  # 延迟导入

            self._client = chromadb.PersistentClient(path=str(self._path))
        return self._client

    def _get_collection(self) -> Any:
        if self._collection is None:
            self._collection = self._get_client().get_or_create_collection(
                COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def add(
        self,
        item_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: dict[str, Any],
    ) -> None:
        if not chunks:
            return
        ids = [f"{item_id}:{idx}" for idx in range(len(chunks))]
        metadatas = [
            _sanitize({**metadata, "item_id": item_id, "chunk_idx": idx})
            for idx in range(len(chunks))
        ]
        self._get_collection().add(
            ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas
        )

    def delete(self, item_id: str) -> None:
        self._get_collection().delete(where={"item_id": item_id})

    def query(
        self,
        embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        collection = self._get_collection()
        kwargs: dict[str, Any] = {"query_embeddings": [embedding], "n_results": top_k}
        if where:
            kwargs["where"] = where
        result = collection.query(**kwargs)

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        out: list[dict[str, Any]] = []
        for i, doc_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            out.append(
                {
                    "id": doc_id,
                    "document": documents[i] if i < len(documents) else "",
                    "metadata": meta,
                    "distance": distances[i] if i < len(distances) else 0.0,
                }
            )
        return out
