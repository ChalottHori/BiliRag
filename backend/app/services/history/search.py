"""对话历史全文检索（SQLite FTS5）。

- 对 `chat_session.title` 与 `chat_message.content` 做全文检索（trigram 分词）。
- 按会话聚合返回命中数与高亮摘录。
- 查询词不足 3 字时退化为 LIKE（trigram 需要 >= 3 字）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from ...models import ChatSession


def _fts_phrase(query: str) -> str:
    cleaned = query.replace('"', " ").strip()
    return f'"{cleaned}"'


def _fts_search(session: Any, query: str, limit: int = 200) -> list[Any]:
    sql = text("""
        SELECT session_id, doc_type, ref_id,
               snippet(chat_message_fts, 1, :open, :close, '…', 12) AS snip
        FROM chat_message_fts
        WHERE chat_message_fts MATCH :q
        ORDER BY rank
        LIMIT :limit
        """)
    rows = session.execute(
        sql, {"q": _fts_phrase(query), "open": "⟦", "close": "⟧", "limit": limit}
    ).fetchall()
    return list(rows)


def _like_search(session: Any, query: str, limit: int = 200) -> list[Any]:
    sql = text("""
        SELECT m.session_id AS session_id, 'message' AS doc_type, m.id AS ref_id,
               m.content AS snip
        FROM chat_message m
        WHERE m.content LIKE :like
        UNION ALL
        SELECT s.id AS session_id, 'title' AS doc_type, s.id AS ref_id, s.title AS snip
        FROM chat_session s
        WHERE s.title LIKE :like
        LIMIT :limit
        """)
    rows = session.execute(sql, {"like": f"%{query}%", "limit": limit}).fetchall()
    return list(rows)


def search_sessions(session: Any, query: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """按会话聚合的全文检索结果。"""
    query = query.strip()
    if not query:
        return {"total": 0, "items": []}

    hits = _fts_search(session, query) if len(query) >= 3 else _like_search(session, query)

    # 按会话聚合
    grouped: dict[str, dict[str, Any]] = {}
    for hit in hits:
        sid = hit.session_id
        entry = grouped.setdefault(sid, {"session_id": sid, "hit_count": 0, "snippets": []})
        entry["hit_count"] += 1
        if len(entry["snippets"]) < 3:
            entry["snippets"].append(hit.snip)

    items = []
    for sid, entry in grouped.items():
        row = session.get(ChatSession, sid)
        if row is None:
            continue
        items.append(
            {
                "session_id": sid,
                "title": row.title,
                "pinned": row.pinned,
                "updated_at": row.updated_at,
                "hit_count": entry["hit_count"],
                "snippets": entry["snippets"],
            }
        )

    # 置顶优先，其余按 updated_at 倒序
    items.sort(key=lambda x: (not x["pinned"], -_ts_key(x["updated_at"])))

    total = len(items)
    start = (page - 1) * page_size
    return {"total": total, "items": items[start : start + page_size]}


def _ts_key(value: Any) -> float:
    return value.timestamp() if value is not None else 0.0
