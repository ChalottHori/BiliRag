"""对话历史 FTS5 检索单测。"""

from __future__ import annotations

import pytest

import app.db as db_module
from app.db import get_session_factory, init_db
from app.models import ChatMessage, ChatSession
from app.services.history import search_sessions


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    monkeypatch.setenv("BILIRAG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(db_module, "_engine", None)
    monkeypatch.setattr(db_module, "_SessionLocal", None)
    init_db()
    return get_session_factory()


def test_search_sessions_fts(session_factory) -> None:
    with session_factory() as s:
        sess = ChatSession(title="如何学习机器学习")
        s.add(sess)
        s.flush()
        s.add(ChatMessage(session_id=sess.id, role="user", content="梯度下降是机器学习的基础算法"))
        s.commit()
        sid = sess.id

    with session_factory() as s:
        result = search_sessions(s, "梯度下降")
        assert result["total"] == 1
        assert result["items"][0]["session_id"] == sid
        assert result["items"][0]["hit_count"] == 1


def test_search_sessions_short_query_like(session_factory) -> None:
    with session_factory() as s:
        sess = ChatSession(title="测试")
        s.add(sess)
        s.flush()
        s.add(ChatMessage(session_id=sess.id, role="user", content="你好世界"))
        s.commit()

    with session_factory() as s:
        result = search_sessions(s, "你好")  # 2 字走 LIKE
        assert result["total"] == 1


def test_search_sessions_empty(session_factory) -> None:
    with session_factory() as s:
        assert search_sessions(s, "") == {"total": 0, "items": []}
