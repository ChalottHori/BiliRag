"""来源一致性校验单测（fake LLM，离线）。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.verify import (
    build_correction_feedback,
    parse_verdict,
    scan_fabricated_bvids,
    verify_answer,
)


class _FakeClient:
    """按预设文本返回的 LLM client（只实现 `complete`）。"""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self, messages: list[dict[str, str]], model: str | None = None, temperature: float = 0.0
    ) -> str:
        self.calls.append({"messages": messages, "model": model, "temperature": temperature})
        return self.response


class _Boom:
    async def complete(self, messages, model=None, temperature=0.0) -> str:
        raise RuntimeError("boom")


def _sources() -> list[dict[str, Any]]:
    return [{"bvid": "BV1aa2bb3cc4", "title": "视频A"}]


def test_scan_fabricated_bvids() -> None:
    assert scan_fabricated_bvids("看 BV1aa2bb3cc4 和 BV9zz8yy7xx6", {"BV1aa2bb3cc4"}) == [
        "BV9zz8yy7xx6"
    ]
    assert scan_fabricated_bvids("无 BV 号", {"BV1aa2bb3cc4"}) == []


def test_parse_verdict_pass() -> None:
    assert parse_verdict('{"verdict": "pass", "issues": []}') == {"verdict": "pass", "issues": []}


def test_parse_verdict_with_code_fence() -> None:
    text = (
        '```json\n{"verdict": "fail", "issues": ['
        '{"type": "fabricated_source", "source": "X", "reason": "r"}]}\n```'
    )
    verdict = parse_verdict(text)
    assert verdict["verdict"] == "fail"
    assert verdict["issues"][0]["type"] == "fabricated_source"


def test_parse_verdict_invalid() -> None:
    assert parse_verdict("不是 JSON") == {"verdict": "unknown", "issues": []}


def test_verify_answer_pass() -> None:
    client = _FakeClient('{"verdict": "pass", "issues": []}')
    verdict = asyncio.run(verify_answer("q", "答案", _sources(), "证据", client, model="qa"))
    assert verdict == {"verdict": "pass", "issues": []}
    assert client.calls[0]["model"] == "qa"
    assert client.calls[0]["temperature"] == 0.0


def test_verify_answer_llm_flags_fabricated() -> None:
    client = _FakeClient(
        '{"verdict": "fail", "issues": ['
        '{"type": "fabricated_source", "source": "《假视频》", "reason": "不在"}]}'
    )
    verdict = asyncio.run(verify_answer("q", "答案", _sources(), "证据", client))
    assert verdict["verdict"] == "fail"
    assert verdict["issues"][0]["type"] == "fabricated_source"


def test_verify_answer_bv_fallback_forces_fail() -> None:
    # LLM 判定 pass，但答案含假 BV → 兜底强制 fail
    client = _FakeClient('{"verdict": "pass", "issues": []}')
    verdict = asyncio.run(verify_answer("q", "答案是 BV9zz8yy7xx6", _sources(), "证据", client))
    assert verdict["verdict"] == "fail"
    assert any(i["type"] == "fabricated_source" for i in verdict["issues"])


def test_verify_answer_llm_failure_is_unknown_but_bv_still_works() -> None:
    # LLM 异常 → unknown（fail-open）
    verdict = asyncio.run(verify_answer("q", "无 BV", _sources(), "证据", _Boom()))
    assert verdict == {"verdict": "unknown", "issues": []}

    # LLM 异常但 BV 兜底命中假 BV → 仍 fail
    verdict = asyncio.run(verify_answer("q", "BV9zz8yy7xx6", _sources(), "证据", _Boom()))
    assert verdict["verdict"] == "fail"


def test_build_correction_feedback() -> None:
    verdict = {
        "verdict": "fail",
        "issues": [
            {"type": "fabricated_source", "source": "《假视频》", "reason": "不在检索结果中"},
            {"type": "unsupported_claim", "claim": "某结论", "reason": "无证据"},
        ],
    }
    text = build_correction_feedback(verdict)
    assert "《假视频》" in text
    assert "某结论" in text
