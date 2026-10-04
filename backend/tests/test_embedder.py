"""embedding 单测（mock 模型 / 网络）。"""

from __future__ import annotations

from typing import Any

from app.services.indexing.embedder import Embedder


class _FakeModel:
    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> list[list[float]]:
        return [[float(len(t))] for t in texts]


def test_embed_local() -> None:
    e = Embedder(model=_FakeModel())
    assert e.embed(["a", "abc"]) == [[1.0], [3.0]]


def test_embed_empty() -> None:
    assert Embedder(model=_FakeModel()).embed([]) == []


def test_embed_api(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3]}]}

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        async def post(self, url: str, json: dict[str, Any] | None = None) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.indexing.embedder.httpx.AsyncClient", FakeClient)
    e = Embedder(provider="api", base_url="http://x/v1", model_name="m", api_key="k")
    result = e.embed(["a", "b"])
    assert result == [[0.1, 0.2], [0.3]]
    assert captured["url"] == "http://x/v1/embeddings"
    assert captured["json"]["input"] == ["a", "b"]
