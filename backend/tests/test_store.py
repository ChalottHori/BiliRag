"""Chroma 向量库封装单测（mock collection）。"""

from __future__ import annotations

from typing import Any

from app.services.indexing.store import VectorStore


class _FakeCollection:
    def __init__(self) -> None:
        self.added: list[tuple[Any, ...]] = []
        self.deleted: list[dict[str, Any]] = []
        self.queried: list[tuple[Any, ...]] = []

    def add(self, ids: Any, embeddings: Any, documents: Any, metadatas: Any) -> None:
        self.added.append((ids, embeddings, documents, metadatas))

    def delete(self, where: dict[str, Any]) -> None:
        self.deleted.append(where)

    def query(self, query_embeddings: Any, n_results: Any, where: Any = None) -> dict[str, Any]:
        self.queried.append((query_embeddings, n_results, where))
        return {
            "ids": [["item1:0"]],
            "documents": [["doc"]],
            "metadatas": [[{"item_id": "item1", "chunk_idx": 0}]],
            "distances": [[0.5]],
        }


def test_add_ids_and_metadata() -> None:
    coll = _FakeCollection()
    store = VectorStore(collection=coll)
    store.add("item1", ["a", "b"], [[0.1], [0.2]], {"folder_id": None, "bvid": "BV1"})

    ids, _emb, _doc, metadatas = coll.added[0]
    assert ids == ["item1:0", "item1:1"]
    assert metadatas[0]["item_id"] == "item1"
    assert metadatas[0]["chunk_idx"] == 0
    assert metadatas[0]["folder_id"] == ""  # None 被归一为 ""
    assert metadatas[0]["bvid"] == "BV1"


def test_delete_uses_item_id_where() -> None:
    coll = _FakeCollection()
    store = VectorStore(collection=coll)
    store.delete("item1")
    assert coll.deleted == [{"item_id": "item1"}]


def test_query_normalizes() -> None:
    coll = _FakeCollection()
    store = VectorStore(collection=coll)
    results = store.query([0.5], top_k=5)
    assert results[0]["id"] == "item1:0"
    assert results[0]["metadata"]["item_id"] == "item1"
    assert results[0]["distance"] == 0.5
