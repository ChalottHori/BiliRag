"""B 站客户端单测（mock 网络，离线）。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx
import pytest

from app.services.bilibili.client import BilibiliClient, BilibiliError


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> BilibiliClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return BilibiliClient(client=http)


def test_get_folders_parses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"list": [{"id": 1, "title": "默认收藏夹", "media_count": 10}]},
            },
        )

    folders = asyncio.run(_client(handler).get_folders("123"))
    assert folders == [
        {"fid": "1", "title": "默认收藏夹", "media_count": 10, "is_watch_later": False}
    ]


def test_business_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": -101, "message": "账号未登录"})

    with pytest.raises(BilibiliError):
        asyncio.run(_client(handler).get_nav())


def test_generate_qrcode() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"code": 0, "data": {"url": "https://x/qr", "qrcode_key": "K123"}}
        )

    result = asyncio.run(_client(handler).generate_qrcode())
    assert result == {"qrcode_url": "https://x/qr", "qrcode_key": "K123"}


def test_video_info_parts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "bvid": "BV1",
                    "aid": 1,
                    "title": "合集",
                    "pic": "http://x/pic",
                    "owner": {"name": "UP"},
                    "pubdate": 1700000000,
                    "duration": 100,
                    "pages": [
                        {"cid": 1, "page": 1, "part": "P1", "duration": 50},
                        {"cid": 2, "page": 2, "part": "P2", "duration": 50},
                    ],
                },
            },
        )

    info = asyncio.run(_client(handler).get_video_info("BV1"))
    assert info["is_collection"] is True
    assert len(info["parts"]) == 2
    assert info["parts"][0]["cid"] == 1


def test_rate_limit_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(429)
        return httpx.Response(200, json={"code": 0, "data": "ok"})

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.services.bilibili.client.asyncio.sleep", fake_sleep)
    client = _client(handler)
    data = asyncio.run(client._get_json("https://api.bilibili.com/x/web-interface/nav"))
    assert data == "ok"
    assert calls["n"] == 3
