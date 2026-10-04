"""wbi 签名单测（纯逻辑）。"""

from __future__ import annotations

import hashlib

from app.services.bilibili.wbi import extract_key_from_url, get_mixin_key, sign_params


def test_extract_key_from_url() -> None:
    url = "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png"
    assert extract_key_from_url(url) == "7cd084941338484aae1ad9425b84077c"


def test_mixin_key_length_and_determinism() -> None:
    img = "a" * 32
    sub = "b" * 32
    assert get_mixin_key(img, sub) == get_mixin_key(img, sub)
    assert len(get_mixin_key(img, sub)) == 32


def test_sign_params_adds_wts_and_wrid() -> None:
    signed = sign_params({"bvid": "BV1xx", "cid": "123"}, "k" * 32, wts=1700000000)
    assert signed["wts"] == 1700000000
    assert signed["bvid"] == "BV1xx"
    assert signed["cid"] == "123"
    assert isinstance(signed["w_rid"], str)
    assert len(signed["w_rid"]) == 32
    expected = "bvid=BV1xx&cid=123&wts=1700000000"
    assert signed["w_rid"] == hashlib.md5((expected + "k" * 32).encode()).hexdigest()


def test_sign_params_filters_special_chars() -> None:
    signed = sign_params({"v": "a!'()*b"}, "k" * 32, wts=1700000000)
    expected = "v=ab&wts=1700000000"
    assert signed["w_rid"] == hashlib.md5((expected + "k" * 32).encode()).hexdigest()
