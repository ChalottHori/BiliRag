"""问答（流式 + 出处引用）与对话历史管理（§7.6）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..config import Settings, load_settings
from ..db import get_session_factory
from ..models import ChatMessage, ChatSession, Item
from ..schemas import ChatMessageRead, ChatSessionRead
from ..services.export import build_session_markdown
from ..services.history import search_sessions
from ..services.indexing import Embedder, VectorStore
from ..services.llm import LLMClient
from .deps import get_db

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str | None = None
    question: str
    filter: dict[str, Any] | None = None


class SessionPatch(BaseModel):
    title: str | None = None
    pinned: bool | None = None


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ------------------------------------------------------------------ 检索 / 提示词
def _build_where(filter_dict: dict[str, Any] | None) -> dict[str, Any] | None:
    if not filter_dict:
        return None
    conditions: list[dict[str, Any]] = []
    folder_ids = filter_dict.get("folder_ids")
    if folder_ids:
        conditions.append({"folder_id": {"$in": list(folder_ids)}})

    time_from = filter_dict.get("time_from")
    time_to = filter_dict.get("time_to")
    if time_from or time_to:
        rng: dict[str, Any] = {}
        if time_from:
            rng["$gte"] = _to_ts(time_from)
        if time_to:
            rng["$lte"] = _to_ts(time_to)
        conditions.append({"pubdate_ts": rng})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _to_ts(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return datetime.fromisoformat(str(value)).timestamp()


def _retrieve(
    settings: Settings, question: str, filter_dict: dict[str, Any] | None
) -> list[dict[str, Any]]:
    embedder = Embedder(
        model_name=settings.embedding_model,
        provider=settings.embedding_provider,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
    embedding = embedder.embed([question])[0]
    store = VectorStore(path=settings.chroma_path)
    return store.query(embedding, top_k=settings.top_k, where=_build_where(filter_dict))


def _build_citations(chunks: list[dict[str, Any]], db: Any) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        item_id = meta.get("item_id")
        item = db.get(Item, item_id) if item_id else None
        citations.append(
            {
                "item_id": item_id or "",
                "bvid": meta.get("bvid", ""),
                "cid": meta.get("cid", ""),
                "title": (item.part_title or item.title) if item else "",
                "chunk_idx": meta.get("chunk_idx", 0),
                "snippet": (chunk.get("document") or "")[:200],
            }
        )
    return citations


def _load_history(db: Any, session_id: str, limit: int = 10) -> list[dict[str, str]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def _build_messages(
    chunks: list[dict[str, Any]], history: list[dict[str, str]], question: str
) -> list[dict[str, str]]:
    system = (
        "你是知识库问答助手。请根据提供的参考资料回答问题，"
        "并在答案中标注引用编号（如 [1][2]）。若资料不足以回答，请如实说明。"
    )
    context = "\n".join(f"[{i}] {c.get('document', '')}" for i, c in enumerate(chunks, 1))
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": f"参考资料：\n{context}\n\n问题：{question}"})
    return messages


def _get_or_create_session(db: Any, session_id: str | None, question: str) -> ChatSession:
    if session_id:
        existing = db.get(ChatSession, session_id)
        if existing is not None:
            return existing
    session = ChatSession(title=question[:30])
    db.add(session)
    db.commit()
    return session


def _save_assistant(session_id: str, answer: str, citations: list[dict[str, Any]]) -> None:
    with get_session_factory()() as session:
        message = ChatMessage(
            session_id=session_id, role="assistant", content=answer, citations_json=citations
        )
        session.add(message)
        row = session.get(ChatSession, session_id)
        if row is not None:
            row.updated_at = datetime.now()
        session.commit()


# ------------------------------------------------------------------ 路由
@router.post("/chat")
async def chat(req: ChatRequest, db: Any = Depends(get_db)) -> StreamingResponse:
    settings = load_settings(db)
    session = _get_or_create_session(db, req.session_id, req.question)

    user_msg = ChatMessage(session_id=session.id, role="user", content=req.question)
    db.add(user_msg)
    if not session.title:
        session.title = req.question[:30]
    db.commit()

    chunks = await run_in_threadpool(_retrieve, settings, req.question, req.filter)
    citations = _build_citations(chunks, db)
    history = _load_history(db, session.id)
    messages = _build_messages(chunks, history, req.question)

    async def gen() -> AsyncIterator[str]:
        collected: list[str] = []
        try:
            client = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
            async for piece in client.stream_complete(messages):
                collected.append(piece)
                yield _sse({"type": "delta", "content": piece})
            answer = "".join(collected)
            _save_assistant(session.id, answer, citations)
            yield _sse({"type": "done", "session_id": session.id, "citations": citations})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "error": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/chat/sessions")
def list_sessions(db: Any = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (
        db.query(ChatSession)
        .order_by(ChatSession.pinned.desc(), ChatSession.updated_at.desc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        count = db.query(ChatMessage).filter(ChatMessage.session_id == row.id).count()
        data = ChatSessionRead.model_validate(row).model_dump()
        data["message_count"] = count
        out.append(data)
    return out


@router.patch("/chat/sessions/{session_id}")
def patch_session(session_id: str, req: SessionPatch, db: Any = Depends(get_db)) -> dict[str, Any]:
    row = db.get(ChatSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    if req.title is not None:
        row.title = req.title
    if req.pinned is not None:
        row.pinned = req.pinned
    db.commit()
    return ChatSessionRead.model_validate(row).model_dump()


@router.get("/chat/sessions/{session_id}/messages")
def list_messages(session_id: str, db: Any = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [ChatMessageRead.model_validate(r).model_dump() for r in rows]


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str, db: Any = Depends(get_db)) -> dict[str, str]:
    row = db.get(ChatSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    db.delete(row)
    db.commit()
    return {"status": "ok"}


@router.get("/chat/search")
def search_chat(q: str, page: int = 1, db: Any = Depends(get_db)) -> dict[str, Any]:
    return search_sessions(db, q, page=page)


@router.post("/chat/sessions/{session_id}/export")
def export_session(session_id: str, db: Any = Depends(get_db)) -> StreamingResponse:
    row = db.get(ChatSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    markdown = build_session_markdown(row, messages)
    filename = f"session-{session_id[:8]}.md"
    return StreamingResponse(
        iter([markdown]),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
