"""结构化摘要：四件套（标题 / 概述 / 要点 / 关键词）+ 长文 map-reduce。"""

from __future__ import annotations

import json
import re
from typing import Any

from .client import LLMClient

_SUMMARY_SYSTEM = (
    "你是视频内容整理助手。请阅读下面的全文稿，输出结构化摘要。"
    "严格只输出一个 JSON 对象，不要任何额外文字或代码块标记，字段如下："
    '{"title": "精炼标题", "overview": "一句话概述", '
    '"points": ["要点1", "要点2", ...], "keywords": ["关键词1", ...]}。'
    "要点 3~10 条，纯文字不含时间戳；关键词 3~8 个。"
)

_CHUNK_SYSTEM = (
    "你是视频内容整理助手。请把下面这段全文稿提炼成若干条要点，"
    "只输出要点列表（每行一条，以 - 开头），不要其他文字。"
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_summary_messages(transcript: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {"role": "user", "content": transcript},
    ]


def build_chunk_summary_messages(chunk: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _CHUNK_SYSTEM},
        {"role": "user", "content": chunk},
    ]


def parse_summary(text: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON；失败时降级为仅保留概述。"""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        return {
            "title": str(data.get("title", "")),
            "overview": str(data.get("overview", "")),
            "points": [str(p) for p in (data.get("points") or [])],
            "keywords": [str(k) for k in (data.get("keywords") or [])],
        }
    except (json.JSONDecodeError, AttributeError):
        pass

    match = _JSON_RE.search(cleaned)
    if match:
        try:
            data = json.loads(match.group(0))
            return {
                "title": str(data.get("title", "")),
                "overview": str(data.get("overview", "")),
                "points": [str(p) for p in (data.get("points") or [])],
                "keywords": [str(k) for k in (data.get("keywords") or [])],
            }
        except json.JSONDecodeError:
            pass

    return {"title": "", "overview": cleaned, "points": [], "keywords": []}


def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 200) -> list[str]:
    """按字符切块，带重叠，用于 map-reduce。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks


async def summarize(
    transcript: str,
    client: LLMClient,
    model: str | None = None,
    chunk_size: int = 4000,
    overlap: int = 200,
) -> dict[str, Any]:
    """生成结构化摘要；超长文稿走 map-reduce。"""
    if len(transcript) <= chunk_size:
        text = await client.complete(build_summary_messages(transcript), model=model)
        return parse_summary(text)

    chunk_summaries: list[str] = []
    for chunk in chunk_text(transcript, chunk_size, overlap):
        text = await client.complete(build_chunk_summary_messages(chunk), model=model)
        chunk_summaries.append(text)

    merged = "\n\n".join(f"【片段{i + 1}】\n{s}" for i, s in enumerate(chunk_summaries))
    text = await client.complete(build_summary_messages(merged), model=model)
    return parse_summary(text)
