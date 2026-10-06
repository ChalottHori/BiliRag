"""VectorStore（langchain_chroma）单测：EphemeralClient + 确定性 FakeEmbeddings。"""

from __future__ import annotations

import hashlib
from typing import Any

import chromadb
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.services.indexing.store import VectorStore


class FakeEmbeddings(Embeddings):
    """确定性假向量：MD5(text) 前 8 字节归一化，离线可复现，不加载真实模型。

    继承 langchain `Embeddings` 接口，同时提供 `embed()`，便于作为
    `VectorStore(embedder=...)` 注入（内部会包成 `LangChainEmbedding` 适配器委托）。
    """

    DIM = 8

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    @staticmethod
    def _vec(text: str) -> list[float]:
        digest = hashlib.md5(text.encode("utf-8")).digest()
        return [float(b) / 255.0 for b in digest[: FakeEmbeddings.DIM]]


def _make_client() -> Any:
    return chromadb.EphemeralClient()


def test_add_writes_documents_with_merged_metadata() -> None:
    client = _make_client()
    store = VectorStore(client=client, embedder=FakeEmbeddings())  # type: ignore[arg-type]

    written = store.add(
        "item1",
        ["你好", "世界"],
        {"folder_id": None, "bvid": "BV1", "cid": 123},
    )

    assert written == 2

    result = client.get_collection("items").get(include=["metadatas", "documents"])
    assert result["ids"] == ["item1:0", "item1:1"]
    assert result["documents"] == ["你好", "世界"]
    assert result["metadatas"][0]["item_id"] == "item1"
    assert result["metadatas"][0]["chunk_idx"] == 0
    assert result["metadatas"][1]["chunk_idx"] == 1
    assert result["metadatas"][0]["folder_id"] == ""  # None 归一为 ""
    assert result["metadatas"][0]["bvid"] == "BV1"
    assert result["metadatas"][0]["cid"] == 123


def test_add_empty_chunks_returns_zero() -> None:
    store = VectorStore(client=_make_client(), embedder=FakeEmbeddings())  # type: ignore[arg-type]
    assert store.add("item1", [], {}) == 0


def test_delete_removes_only_target_item() -> None:
    client = _make_client()
    store = VectorStore(client=client, embedder=FakeEmbeddings())  # type: ignore[arg-type]

    store.add("item1", ["a", "b"], {"bvid": "BV1"})
    store.add("item2", ["c"], {"bvid": "BV2"})
    store.delete("item1")

    result = client.get_collection("items").get(include=["metadatas"])
    assert set(result["ids"]) == {"item2:0"}
    assert result["metadatas"][0]["item_id"] == "item2"


def test_search_mmr_returns_documents() -> None:
    client = _make_client()
    store = VectorStore(client=client, embedder=FakeEmbeddings())  # type: ignore[arg-type]
    store.add("item1", ["hello world", "second chunk"], {"bvid": "BV1"})

    docs = store.search_mmr("hello", k=2, fetch_k=4, lambda_mult=0.5, where=None)

    assert len(docs) == 2
    for doc in docs:
        assert isinstance(doc, Document)
    assert all(doc.metadata["item_id"] == "item1" for doc in docs)
    assert {doc.metadata["chunk_idx"] for doc in docs} == {0, 1}


def test_search_mmr_respects_where_filter() -> None:
    client = _make_client()
    store = VectorStore(client=client, embedder=FakeEmbeddings())  # type: ignore[arg-type]
    store.add("item1", ["quantum physics"], {"folder_id": "A", "bvid": "BV1"})
    store.add("item2", ["quantum physics"], {"folder_id": "B", "bvid": "BV2"})

    docs = store.search_mmr(
        "quantum",
        k=2,
        fetch_k=4,
        lambda_mult=0.5,
        where={"folder_id": "A"},
    )

    assert len(docs) == 1
    assert docs[0].metadata["item_id"] == "item1"
    assert docs[0].metadata["folder_id"] == "A"
