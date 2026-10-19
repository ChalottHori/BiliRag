"""ReAct 多跳循环单测（fake LLM + fake 工具，离线）。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.documents import Document

from app.services.react import ToolOutcome, run_react


def _tool_call(call_id: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


class _FakeLLM:
    """按脚本返回 assistant message（含 tool_calls）；tools=None 时返回最终答案。"""

    def __init__(self, script: list[dict[str, Any]], final_content: str = "最终答案"):
        self.script = list(script)
        self.final_content = final_content
        self.calls: list[dict[str, Any]] = []

    async def complete_message(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        if tools is None:
            return {"role": "assistant", "content": self.final_content}
        if not self.script:
            return {"role": "assistant", "content": ""}
        return self.script.pop(0)


def _doc(
    bvid: str, item_id: str, chunk_idx: int, text: str, *, doc_type: str = "chunk"
) -> Document:
    return Document(
        page_content=text,
        metadata={
            "item_id": item_id,
            "bvid": bvid,
            "cid": 1,
            "title": f"《{bvid}》",
            "doc_type": doc_type,
            "chunk_idx": chunk_idx,
        },
    )


async def _search_tool(args: dict[str, Any]) -> ToolOutcome:
    return ToolOutcome(observation="检索结果", docs=[_doc("BV1", "i1", 0, "片段一")])


async def _summary_tool(args: dict[str, Any]) -> ToolOutcome:
    return ToolOutcome(observation="摘要", docs=[_doc("BV1", "i1", -1, "概述", doc_type="summary")])


def test_react_immediate_answer() -> None:
    client = _FakeLLM([{"role": "assistant", "content": "直接答案"}])
    outcome = asyncio.run(run_react("问题", [], client, {}))
    assert outcome.answer == "直接答案"
    assert outcome.citations == []
    assert outcome.sources == []
    assert outcome.fell_back is False


def test_react_normal_multihop() -> None:
    client = _FakeLLM(
        [
            _tool_call("c1", "search", {"query": "X"}),
            _tool_call("c2", "read_summary", {"bvid": "BV1"}),
            {"role": "assistant", "content": "综合答案"},
        ]
    )
    tools = {"search": _search_tool, "read_summary": _summary_tool}
    steps: list[dict[str, Any]] = []
    outcome = asyncio.run(run_react("问题", [], client, tools, on_step=steps.append))
    assert outcome.answer == "综合答案"
    assert outcome.fell_back is False
    # 跨步按 bvid 去重：两个工具都命中 BV1 -> 1 个来源
    assert [s["bvid"] for s in outcome.sources] == ["BV1"]
    # 两个不同 chunk 身份 -> 2 条引用
    assert len(outcome.citations) == 2
    # docs 暴露给来源一致性校验作证据
    assert len(outcome.docs) == 2
    assert [s["kind"] for s in steps] == ["tool_call", "observation", "tool_call", "observation"]


def test_react_max_rounds_forces_answer() -> None:
    client = _FakeLLM(
        [
            _tool_call("c1", "search", {"query": "X"}),
            _tool_call("c2", "search", {"query": "Y"}),
        ],
        final_content="强制答案",
    )
    calls: list[dict[str, Any]] = []

    async def search(args: dict[str, Any]) -> ToolOutcome:
        calls.append(args)
        return ToolOutcome(observation="r")

    outcome = asyncio.run(run_react("问题", [], client, {"search": search}, max_rounds=2))
    assert outcome.answer == "强制答案"
    assert len(calls) == 2


def test_react_repeat_call_forces_answer() -> None:
    client = _FakeLLM(
        [
            _tool_call("c1", "search", {"query": "X"}),
            _tool_call("c2", "search", {"query": "X"}),
        ],
        final_content="强制答案",
    )
    calls: list[dict[str, Any]] = []

    async def search(args: dict[str, Any]) -> ToolOutcome:
        calls.append(args)
        return ToolOutcome(observation="r")

    outcome = asyncio.run(run_react("问题", [], client, {"search": search}))
    assert outcome.answer == "强制答案"
    assert len(calls) == 1  # 第 2 次重复未执行，直接强制结束


def test_react_exception_falls_back() -> None:
    client = _FakeLLM([_tool_call("c1", "search", {"query": "X"})])

    async def search(args: dict[str, Any]) -> ToolOutcome:
        raise RuntimeError("boom")

    outcome = asyncio.run(run_react("问题", [], client, {"search": search}))
    assert outcome.fell_back is True
    assert outcome.answer == ""


def test_react_truncates_old_observations() -> None:
    script = [_tool_call(f"c{i}", "search", {"query": f"Q{i}"}) for i in range(4)]
    script.append({"role": "assistant", "content": "答案"})
    client = _FakeLLM(script)

    async def search(args: dict[str, Any]) -> ToolOutcome:
        return ToolOutcome(observation=f"obs-{args['query']}")

    asyncio.run(run_react("问题", [], client, {"search": search}))
    last_messages = client.calls[-1]["messages"]
    tool_contents = [m["content"] for m in last_messages if m.get("role") == "tool"]
    assert tool_contents[0] == "（早期检索结果已截断）"
    assert tool_contents[-1] == "obs-Q3"
