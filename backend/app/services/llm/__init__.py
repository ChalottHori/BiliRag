"""LLM 服务（OpenAI 兼容）：摘要、map-reduce、流式问答。"""

from __future__ import annotations

from .client import LLMClient
from .summarize import chunk_text, parse_summary, summarize

__all__ = ["LLMClient", "chunk_text", "parse_summary", "summarize"]
