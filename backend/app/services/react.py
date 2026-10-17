"""ReAct 多跳检索循环（原生 function calling）。

纯逻辑 + 可注入依赖（LLM 客户端 / 工具执行器），便于 fake 单测。
循环内的 assistant(tool_calls) 与 role="tool" 消息仅存活于本次请求，不落库。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document

from .retrieval import document_identity

MAX_ROUNDS = 5  # 最多 5 轮 LLM 往返（1 首轮 + 4 工具轮）
REPEAT_LIMIT = 2  # 同「工具+参数」第 2 次重复即强制结束
MAX_OBSERVATION_ROUNDS = 3  # 观察上下文：保留最近 3 轮 tool 消息
MAX_OBSERVATION_CHARS = 8000  # 单条 observation 内容上限
SOURCES_LIMIT = 5
CITATIONS_LIMIT = 8

SYSTEM_PROMPT = (
    "你是一个 B 站知识库问答助手，可调用工具检索用户收藏的视频内容。\n"
    "规则：\n"
    "1. 优先用 search 检索；一次检索不够时，换关键词再次 search。\n"
    "2. 定位到具体视频后，可用 read_summary / read_transcript 深挖细节。\n"
    "3. 信息充分后直接作答，不要再调用工具。"
)

FORCE_ANSWER_PROMPT = "请基于以上检索到的内容直接回答用户问题，不要再调用工具。"


def _tool_schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOL_DEFS: list[dict[str, Any]] = [
    _tool_schema(
        "search",
        "在知识库中检索与查询相关的内容片段（标题 + 片段）",
        {"query": {"type": "string", "description": "检索查询词"}},
        ["query"],
    ),
    _tool_schema(
        "read_summary",
        "读取某个视频的摘要（概述与要点）",
        {"bvid": {"type": "string", "description": "视频 BV 号"}},
        ["bvid"],
    ),
    _tool_schema(
        "read_transcript",
        "读取某个视频字幕中与查询最相关的片段",
        {
            "bvid": {"type": "string", "description": "视频 BV 号"},
            "query": {
                "type": ["string", "null"],
                "description": "关注的查询词，为空则取开头片段",
            },
        },
        ["bvid"],
    ),
]


@dataclass
class ToolOutcome:
    """一次工具调用的结果：observation 喂回模型，docs 用于引用聚合。"""

    observation: str
    docs: list[Document] = field(default_factory=list)


ToolFn = Callable[[dict[str, Any]], Awaitable[ToolOutcome]]


@dataclass
class ReactOutcome:
    answer: str
    citations: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    fell_back: bool = False


def _preview(text: str, max_length: int = 200) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if len(value) > max_length:
        value = value[:max_length].rstrip() + "..."
    return value


def _cap_observation(text: str) -> str:
    if len(text) <= MAX_OBSERVATION_CHARS:
        return text
    return text[:MAX_OBSERVATION_CHARS].rstrip() + "\n（内容过长已截断）"


def _build_citations(docs: list[Document]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for doc in docs:
        key = document_identity(doc)
        if key in seen:
            continue
        seen.add(key)
        meta = doc.metadata or {}
        out.append(
            {
                "item_id": meta.get("item_id", ""),
                "bvid": meta.get("bvid", ""),
                "cid": meta.get("cid", 0),
                "title": meta.get("title", ""),
                "snippet": _preview(doc.page_content or "", 200),
            }
        )
        if len(out) >= CITATIONS_LIMIT:
            break
    return out


def _build_sources(docs: list[Document]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for doc in docs:
        meta = doc.metadata or {}
        bvid = meta.get("bvid", "")
        if not bvid or bvid in seen:
            continue
        seen.add(bvid)
        out.append(
            {
                "bvid": bvid,
                "title": meta.get("title", ""),
                "url": meta.get("url") or f"https://www.bilibili.com/video/{bvid}",
                "snippet": _preview(doc.page_content or "", 200),
            }
        )
        if len(out) >= SOURCES_LIMIT:
            break
    return out


def _tool_call_label(name: str, args: dict[str, Any]) -> str:
    if name == "search":
        return f"正在检索知识库「{args.get('query', '')}」"
    if name == "read_summary":
        return f"正在读取 {args.get('bvid', '')} 摘要"
    if name == "read_transcript":
        return f"正在读取 {args.get('bvid', '')} 字幕"
    return f"正在调用 {name}"


def _observation_label(name: str, outcome: ToolOutcome) -> str:
    n = len(outcome.docs)
    if name == "search":
        return f"检索到 {n} 条片段"
    if name == "read_summary":
        return "已读取摘要"
    if name == "read_transcript":
        return f"命中 {n} 段相关片段"
    return "完成"


def _truncate_observations(messages: list[dict[str, Any]]) -> None:
    """保留最近 MAX_OBSERVATION_ROUNDS 条 tool 消息，更早的折叠为占位。

    保留消息本身（不改结构），避免破坏 assistant tool_calls 与 tool 结果的
    tool_call_id 配对。
    """
    tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    overflow = len(tool_indices) - MAX_OBSERVATION_ROUNDS
    for i in tool_indices[:overflow]:
        messages[i]["content"] = "（早期检索结果已截断）"


def _finish(answer: str, doc_groups: list[list[Document]]) -> ReactOutcome:
    docs = [doc for group in doc_groups for doc in group]
    return ReactOutcome(
        answer=answer,
        citations=_build_citations(docs),
        sources=_build_sources(docs),
    )


async def _force_answer(
    client: Any, messages: list[dict[str, Any]], doc_groups: list[list[Document]]
) -> ReactOutcome:
    messages.append({"role": "user", "content": FORCE_ANSWER_PROMPT})
    msg = await client.complete_message(messages)
    return _finish(msg.get("content") or "", doc_groups)


async def run_react(
    question: str,
    history: list[dict[str, str]],
    client: Any,
    tools: dict[str, ToolFn],
    *,
    on_step: Callable[[dict[str, Any]], None] | None = None,
    max_rounds: int = MAX_ROUNDS,
) -> ReactOutcome:
    """执行 ReAct 多跳循环，返回最终答案与聚合引用。

    `client` 只需实现 `complete_message(messages, model=None, temperature=0.0,
    tools=None, tool_choice=None) -> dict`（返回 assistant message）。
    任何异常都转 `fell_back=True`，由调用方降级单跳。
    """
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    doc_groups: list[list[Document]] = []
    repeat_counts: dict[str, int] = {}

    def emit(kind: str, tool: str, label: str) -> None:
        if on_step:
            on_step({"kind": kind, "tool": tool, "label": label})

    try:
        for _ in range(max_rounds):
            msg = await client.complete_message(messages, tools=TOOL_DEFS, tool_choice="auto")
            msg.setdefault("role", "assistant")
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return _finish(msg.get("content") or "", doc_groups)

            messages.append(msg)
            for call in tool_calls:
                fn = call.get("function") or {}
                name = fn.get("name", "")
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if args_str else {}
                except json.JSONDecodeError:
                    args = {}

                if name not in tools:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id", ""),
                            "content": "（未知工具，已忽略）",
                        }
                    )
                    continue

                key = f"{name}:{args_str}"
                repeat_counts[key] = repeat_counts.get(key, 0) + 1
                if repeat_counts[key] >= REPEAT_LIMIT:
                    return await _force_answer(client, messages, doc_groups)

                emit("tool_call", name, _tool_call_label(name, args))
                outcome = await tools[name](args)
                doc_groups.append(outcome.docs)
                emit("observation", name, _observation_label(name, outcome))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": _cap_observation(outcome.observation),
                    }
                )
                _truncate_observations(messages)

        return await _force_answer(client, messages, doc_groups)
    except Exception:
        return ReactOutcome(answer="", citations=[], sources=[], fell_back=True)
