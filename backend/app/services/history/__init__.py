"""对话历史：FTS5 标题+内容检索，按会话聚合返回命中数与摘录。"""

from __future__ import annotations

from .search import search_sessions

__all__ = ["search_sessions"]
