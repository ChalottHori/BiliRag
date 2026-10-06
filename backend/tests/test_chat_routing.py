"""四路路由规则与 LLM 路由单测。"""

from __future__ import annotations

import asyncio

from app.api.chat import (
    _is_collection_intent,
    _is_general_question,
    _is_list_question,
    _is_summary_question,
    _route_with_llm,
    _route_with_rules,
)


class _FakeRouterClient:
    """mock LLM 客户端：可编程返回文本或抛异常。"""

    def __init__(self, result: str = "", exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        if self._exc is not None:
            raise self._exc
        return self._result


# ---------- 规则函数 ----------


def test_is_general_question() -> None:
    assert _is_general_question("你好") is True
    assert _is_general_question("谢谢") is True
    assert _is_general_question("你是谁") is True
    assert _is_general_question("量子力学是什么") is False


def test_is_list_question() -> None:
    assert _is_list_question("有哪些视频") is True
    assert _is_list_question("列出所有条目") is True
    assert _is_list_question("量子力学") is False


def test_is_summary_question() -> None:
    assert _is_summary_question("总结一下") is True
    assert _is_summary_question("讲些什么") is True
    assert _is_summary_question("有哪些视频") is False


def test_is_collection_intent() -> None:
    assert _is_collection_intent("收藏夹里有什么") is True
    assert _is_collection_intent("视频内容") is True
    assert _is_collection_intent("量子力学") is False


def test_route_with_rules() -> None:
    assert _route_with_rules("你好", False, False) == "direct"
    assert _route_with_rules("有哪些视频", False, False) == "db_list"
    assert _route_with_rules("总结一下", False, False) == "db_content"
    # 无相关性且无收藏意图 -> direct
    assert _route_with_rules("量子力学", False, False) == "direct"
    # 收藏意图或已命中库 -> vector
    assert _route_with_rules("量子力学", True, False) == "vector"
    assert _route_with_rules("量子力学", False, True) == "vector"


# ---------- _route_with_llm ----------


def test_route_with_llm_picks_one_of_four() -> None:
    for route in ("direct", "db_list", "db_content", "vector"):
        parsed, raw = asyncio.run(_route_with_llm("问题", _FakeRouterClient(route)))
        assert parsed == route
        assert raw == route


def test_route_with_llm_regex_fallback() -> None:
    parsed, raw = asyncio.run(
        _route_with_llm("问题", _FakeRouterClient("我认为应该走 db_content 路由"))
    )
    assert parsed == "db_content"
    assert "db_content" in raw


def test_route_with_llm_no_match_returns_none() -> None:
    parsed, raw = asyncio.run(_route_with_llm("问题", _FakeRouterClient("乱七八糟")))
    assert parsed is None
    assert raw == "乱七八糟"


def test_route_with_llm_failure_falls_back() -> None:
    parsed, raw = asyncio.run(_route_with_llm("问题", _FakeRouterClient(exc=RuntimeError("boom"))))
    assert parsed is None
    assert raw == ""
