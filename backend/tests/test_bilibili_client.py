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


def test_poll_qrcode_captures_login_cookies() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/poll" in request.url.path:
            # poll 成功：返回 crossDomain URL（ticket 换 cookie）
            return httpx.Response(
                200,
                json={"code": 0, "data": {"url": "https://passport.biligame.com/x/passport-login/web/crossDomain?ticket=t"}},
            )
        # crossDomain：302 + 跨域 Set-Cookie（Domain=.bilibili.com）
        return httpx.Response(
            302,
            headers={
                "Set-Cookie": "SESSDATA=abc%2Cdef; Domain=.bilibili.com; Path=/; HttpOnly",
                "Location": "https://www.bilibili.com/",
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    client = BilibiliClient(client=http)
    result = asyncio.run(client.poll_qrcode("K1"))
    assert result["code"] == 0
    assert result["cookies"] == {"SESSDATA": "abc%2Cdef"}
    assert client.cookies == {"SESSDATA": "abc%2Cdef"}


def test_generate_qrcode() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"code": 0, "data": {"url": "https://x/qr", "qrcode_key": "K123"}}
        )

    result = asyncio.run(_client(handler).generate_qrcode())
    assert result == {"qrcode_url": "https://x/qr", "qrcode_key": "K123"}


def test_get_folder_videos_parses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "info": {"media_count": 2},
                    "medias": [
                        {
                            "id": 123,
                            "type": 2,
                            "page": 3,
                            "title": "收藏视频",
                            "cover": "http://i0.hdslb.com/bfs/archive/c.jpg",
                            "upper": {"mid": 1, "name": "UP主"},
                            "duration": 90,
                            "pubtime": 1700000000,
                            "bvid": "BV1",
                            "attr": 0,
                        },
                        {
                            "id": 456,
                            "type": 2,
                            "page": 1,
                            "title": "已失效",
                            "cover": "http://i0.hdslb.com/bfs/archive/d.jpg",
                            "upper": {"mid": 2, "name": "UP2"},
                            "duration": 30,
                            "pubtime": 1700000001,
                            "bvid": "BV2",
                            "attr": 9,
                        },
                    ],
                },
            },
        )

    result = asyncio.run(_client(handler).get_folder_videos("100"))
    assert result["total"] == 2
    v0 = result["videos"][0]
    assert v0["bvid"] == "BV1"
    assert v0["aid"] == 123
    assert v0["up_name"] == "UP主"
    assert v0["cover_url"] == "http://i0.hdslb.com/bfs/archive/c.jpg"
    assert v0["pubdate"] == 1700000000
    assert v0["is_invalid"] is False
    assert v0["is_collection"] is True
    assert result["videos"][1]["is_invalid"] is True
    assert result["videos"][1]["is_collection"] is False


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
