"""问答（流式 + 出处引用）与对话历史管理（§7.6）。

检索升级后：混合检索（MMR 向量 + SQLite 关键词 + RRF 融合）+ 四路路由
（direct / db_list / db_content / vector）+ 流式 trace 事件（route / retrieval / sources）。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.documents import Document
from pydantic import BaseModel
from sqlalchemy import or_

from ..config import Settings, load_settings
from ..db import get_session_factory
from ..models import ChatMessage, ChatSession, Item
from ..schemas import ChatMessageRead, ChatSessionRead
from ..services.export import build_session_markdown
from ..services.history import search_sessions
from ..services.indexing import Embedder, VectorStore
from ..services.llm import LLMClient
from ..services.retrieval import (
    RETRIEVAL_CANDIDATE_K,
    RETRIEVAL_MMR_FETCH_K,
    RETRIEVAL_MMR_LAMBDA,
    build_snippet,
    extract_keywords,
    keyword_score,
    merge_ranked_documents,
)
from .deps import get_db

router = APIRouter(prefix="/api", tags=["chat"])

_ROUTE_LABELS = {
    "direct": "直接回答",
    "db_list": "读取收藏夹清单",
    "db_content": "汇总收藏夹内容",
    "vector": "检索知识库",
}

ProgressCallback = Callable[[dict[str, Any]], None] | None


class ChatRequest(BaseModel):
    session_id: str | None = None
    question: str
    filter: dict[str, Any] | None = None


class SessionPatch(BaseModel):
    title: str | None = None
    pinned: bool | None = None


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ------------------------------------------------------------------ 通用工具
def _route_label(route: str) -> str:
    return _ROUTE_LABELS.get(route, route)


def _emit_progress(callback: ProgressCallback, event_type: str, **payload: Any) -> None:
    if callback:
        callback({"type": event_type, **payload})


def _preview(text: str, max_length: int = 220) -> str:
    """压平空白并截断出可展示的片段预览。"""
    preview = re.sub(r"\s+", " ", text or "").strip()
    if len(preview) > max_length:
        preview = preview[:max_length].rstrip() + "..."
    return preview


def _to_ts(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return datetime.fromisoformat(str(value)).timestamp()


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value))
    return datetime.fromisoformat(str(value))


def _build_where(filter_dict: dict[str, Any] | None) -> dict[str, Any] | None:
    """把 filter 转成 Chroma where：范围（收藏夹 ∪ 视频，并集）且时间区间。

    收藏夹与视频两个维度是并集，用 `$or` 合成；时间范围与范围是 `$and`。
    """
    if not filter_dict:
        return None

    scope_conditions: list[dict[str, Any]] = []
    folder_ids = filter_dict.get("folder_ids")
    if folder_ids:
        scope_conditions.append({"folder_id": {"$in": list(folder_ids)}})
    bvids = filter_dict.get("bvids")
    if bvids:
        scope_conditions.append({"bvid": {"$in": list(bvids)}})

    scope: dict[str, Any] | None = None
    if len(scope_conditions) == 1:
        scope = scope_conditions[0]
    elif len(scope_conditions) > 1:
        scope = {"$or": scope_conditions}

    time_from = filter_dict.get("time_from")
    time_to = filter_dict.get("time_to")
    time_cond: dict[str, Any] | None = None
    if time_from or time_to:
        rng: dict[str, Any] = {}
        if time_from:
            rng["$gte"] = _to_ts(time_from)
        if time_to:
            rng["$lte"] = _to_ts(time_to)
        time_cond = {"pubdate_ts": rng}

    if scope and time_cond:
        return {"$and": [scope, time_cond]}
    return scope or time_cond


def _apply_scope(query: Any, folder_ids: list[str] | None, bvids: list[str] | None) -> Any:
    """按范围（收藏夹 ∪ 视频，并集）过滤查询；空范围 = 不限。"""
    if folder_ids and bvids:
        return query.filter(or_(Item.folder_id.in_(list(folder_ids)), Item.bvid.in_(list(bvids))))
    if folder_ids:
        return query.filter(Item.folder_id.in_(list(folder_ids)))
    if bvids:
        return query.filter(Item.bvid.in_(list(bvids)))
    return query


# ------------------------------------------------------------------ 路由规则（照搬项目二）
def _is_list_question(question: str) -> bool:
    """列表/清单类问题。"""
    list_terms = [
        "有哪些",
        "有什么",
        "列表",
        "清单",
        "目录",
        "都有哪些",
        "列出",
        "罗列",
        "多少个",
        "几个",
    ]
    return any(term in question for term in list_terms)


def _is_summary_question(question: str) -> bool:
    """总结/概括类问题。"""
    summary_terms = [
        "总结",
        "概述",
        "概括",
        "分析",
        "梳理",
        "提炼",
        "回顾",
        "复盘",
        "要点",
        "重点",
        "关键点",
        "核心",
        "讲了什么",
        "讲些什么",
    ]
    return any(term in question for term in summary_terms)


def _is_general_question(question: str) -> bool:
    """通用闲聊/与知识库无关的问题。"""
    general_terms = [
        "你好",
        "嗨",
        "哈喽",
        "hello",
        "hi",
        "ok",
        "在吗",
        "你是谁",
        "你能做什么",
        "谢谢",
        "好的",
        "好",
        "收到",
        "明白",
        "可以",
        "嗯",
        "嗯嗯",
        "晚安",
        "早安",
        "早上好",
    ]
    cleaned = re.sub(r"[\W_]+", "", question, flags=re.UNICODE)
    residual = cleaned.lower()
    for term in general_terms:
        residual = residual.replace(term.lower(), "")
    return residual == ""


def _is_collection_intent(question: str) -> bool:
    """是否显式指向收藏/视频/知识库。"""
    terms = [
        "收藏",
        "收藏夹",
        "视频",
        "合集",
        "up主",
        "BV",
        "bv",
        "分P",
        "字幕",
        "知识库",
        "入库",
        "同步",
        "向量",
        "检索",
    ]
    return any(term in question for term in terms)


def _route_with_rules(question: str, is_collection_intent: bool, related: bool) -> str:
    """规则路由兜底。"""
    if _is_general_question(question):
        return "direct"
    if _is_list_question(question):
        return "db_list"
    if _is_summary_question(question):
        return "db_content"
    if not related and not is_collection_intent:
        return "direct"
    return "vector"


async def _route_with_llm(question: str, client: Any) -> tuple[str | None, str]:
    """使用 LLM 做路由判断（temperature=0，四选一 + 正则兜底），失败回退 (None, "")。"""
    try:
        system = (
            "你是一个路由器，只输出以下之一：direct, db_list, db_content, vector。\n"
            "规则：\n"
            "- direct：寒暄/闲聊/与知识库无关的问题\n"
            "- db_list：清单/列表/目录/有哪些\n"
            "- db_content：明确要求“全部/所有/整体/概览/全库”内容的总结\n"
            "- vector：具体主题问题或需要“先检索再总结”的问题\n"
            "只输出一个词，不要解释。"
        )
        text = await client.complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            temperature=0,
        )
        text = (text or "").strip()
        match = re.search(r"(direct|db_list|db_content|vector)", text)
        return (match.group(1) if match else None), text
    except Exception:  # noqa: BLE001  LLM 路由失败回退规则
        return None, ""


# ------------------------------------------------------------------ 关键词 SQL 通道
def _build_keyword_document(
    item: Item,
    title: str,
    keywords: list[str],
    score: float,
) -> Document:
    """把一次关键词命中组织成一条伪文档（metadata 供 citation / 来源解析）。"""
    parts = [f"视频标题：{title}"]
    if item.up_name:
        parts.append(f"UP主：{item.up_name}")
    snippet = build_snippet(item.transcript or "", keywords)
    if snippet:
        parts.append("相关片段：" + snippet)
    return Document(
        page_content="\n".join(parts),
        metadata={
            "item_id": item.id,
            "bvid": item.bvid,
            "cid": item.cid,
            "title": title,
            "doc_type": "keyword",
            "chunk_idx": -2,
            "url": f"https://www.bilibili.com/video/{item.bvid}",
            "keyword_score": score,
        },
    )


async def _keyword_search_docs(
    db: Any,
    folder_ids: list[str] | None,
    bvids: list[str] | None,
    question: str,
    limit: int,
    filter_dict: dict[str, Any] | None = None,
) -> list[Document]:
    """从 SQLite 按关键词加权召回视频（每个 item 取最高分一条）。"""
    if limit <= 0:
        return []
    keywords = extract_keywords(question)
    if not keywords:
        return []

    like_conds: list[Any] = []
    for kw in keywords:
        pattern = f"%{kw}%"
        like_conds.append(Item.title.ilike(pattern))
        like_conds.append(Item.part_title.ilike(pattern))
        like_conds.append(Item.up_name.ilike(pattern))
        like_conds.append(Item.transcript.ilike(pattern))

    query = db.query(Item).filter(Item.status == "done")
    query = _apply_scope(query, folder_ids, bvids)
    query = query.filter(or_(*like_conds))

    if filter_dict:
        time_from = filter_dict.get("time_from")
        time_to = filter_dict.get("time_to")
        if time_from:
            query = query.filter(Item.pubdate >= _to_datetime(time_from))
        if time_to:
            query = query.filter(Item.pubdate <= _to_datetime(time_to))

    rows = query.limit(max(limit * 4, 40)).all()

    docs_by_item: dict[str, Document] = {}
    scores_by_item: dict[str, float] = {}
    for item in rows:
        if not item.bvid:
            continue
        display_title = item.part_title or item.title
        score_title = " ".join(part for part in (item.part_title, item.title) if part)
        score = keyword_score(
            keywords,
            title=score_title,
            content=item.transcript or "",
            owner_name=item.up_name or "",
        )
        if score <= 0:
            continue
        if score <= scores_by_item.get(item.id, 0.0):
            continue
        scores_by_item[item.id] = score
        docs_by_item[item.id] = _build_keyword_document(item, display_title, keywords, score)

    return sorted(
        docs_by_item.values(),
        key=lambda doc: doc.metadata.get("keyword_score", 0.0),
        reverse=True,
    )[:limit]


async def _is_related_to_collection(
    db: Any,
    folder_ids: list[str] | None,
    bvids: list[str] | None,
    question: str,
) -> bool:
    """判断问题是否与知识库内容相关（关键词 LIKE 命中标题/UP主/正文）。"""
    keywords = extract_keywords(question)
    if not keywords:
        return False
    like_conds: list[Any] = []
    for kw in keywords:
        pattern = f"%{kw}%"
        like_conds.append(Item.title.ilike(pattern))
        like_conds.append(Item.part_title.ilike(pattern))
        like_conds.append(Item.up_name.ilike(pattern))
        like_conds.append(Item.transcript.ilike(pattern))
    query = db.query(Item).filter(Item.status == "done")
    query = _apply_scope(query, folder_ids, bvids)
    return query.filter(or_(*like_conds)).count() > 0


# ------------------------------------------------------------------ 混合检索
async def _retrieve(
    settings: Settings,
    question: str,
    db: Any,
    folder_ids: list[str] | None,
    bvids: list[str] | None,
    filter_dict: dict[str, Any] | None,
) -> tuple[list[Document], int, int]:
    """混合检索：向量 MMR + SQLite 关键词并发召回，RRF 融合后返回 (docs, 向量数, 关键词数)。"""
    embedder = Embedder(
        model_name=settings.embedding_model,
        provider=settings.embedding_provider,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
    store = VectorStore(path=settings.chroma_path, embedder=embedder)
    top_k = max(1, settings.top_k)
    vector_task = asyncio.to_thread(
        store.search_mmr,
        question,
        top_k,
        RETRIEVAL_MMR_FETCH_K,
        RETRIEVAL_MMR_LAMBDA,
        _build_where(filter_dict),
    )
    keyword_task = _keyword_search_docs(
        db, folder_ids, bvids, question, limit=RETRIEVAL_CANDIDATE_K, filter_dict=filter_dict
    )
    vector_docs, keyword_docs = await asyncio.gather(vector_task, keyword_task)
    docs = merge_ranked_documents(
        {"vector": vector_docs, "keyword": keyword_docs},
        top_k=top_k,
        channel_weights={"vector": 1.0, "keyword": 0.9},
        per_video_limit=2,
    )
    return docs, len(vector_docs), len(keyword_docs)


# ------------------------------------------------------------------ 上下文 / 引用
def _doc_title(db: Any, doc: Document) -> str:
    meta = doc.metadata or {}
    if meta.get("title"):
        return meta["title"]
    item_id = meta.get("item_id")
    if item_id:
        item = db.get(Item, item_id)
        if item is not None:
            return item.part_title or item.title
    return ""


def _build_citations(docs: list[Document], db: Any) -> list[dict[str, Any]]:
    """从融合后的文档建引用，兼容 `doc_type=chunk` 与 `doc_type=keyword`。"""
    citations: list[dict[str, Any]] = []
    for doc in docs:
        meta = doc.metadata or {}
        item_id = meta.get("item_id")
        item = db.get(Item, item_id) if item_id else None
        title = meta.get("title") or ((item.part_title or item.title) if item else "")
        citations.append(
            {
                "item_id": item_id or "",
                "bvid": meta.get("bvid") or (item.bvid if item else ""),
                "cid": meta.get("cid") or (item.cid if item else 0),
                "title": title,
                "snippet": _preview(doc.page_content or "", 200),
            }
        )
    return citations


def _has_done_items(db: Any, folder_ids: list[str] | None, bvids: list[str] | None = None) -> bool:
    query = db.query(Item).filter(Item.status == "done")
    query = _apply_scope(query, folder_ids, bvids)
    return query.count() > 0


def _get_db_list_context(
    db: Any,
    folder_ids: list[str] | None,
    bvids: list[str] | None = None,
    limit: int = 50,
) -> tuple[str, list[dict[str, Any]]]:
    """列表路由上下文：标题/分P标题 + 概述（限 50 条），按 bvid 去重。"""
    if not folder_ids and not bvids:
        return "", []
    query = db.query(Item).filter(Item.status == "done")
    query = _apply_scope(query, folder_ids, bvids)
    rows = query.limit(limit).all()
    if not rows:
        return "", []

    lines: list[str] = []
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        if not item.bvid or item.bvid in seen:
            continue
        seen.add(item.bvid)
        title = item.part_title or item.title
        overview = (item.summary_json or {}).get("overview", "")
        line = f"- 《{title}》"
        if overview:
            line += f"（{_preview(overview, 100)}）"
        lines.append(line)
        sources.append(
            {
                "bvid": item.bvid,
                "title": title,
                "url": f"https://www.bilibili.com/video/{item.bvid}",
                "snippet": _preview(overview, 200),
            }
        )
    return "\n".join(lines), sources


def _get_db_content_context(
    db: Any,
    folder_ids: list[str] | None,
    bvids: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """汇总路由上下文：summary_json 的 overview + points 拼接，不限条数。"""
    if not folder_ids and not bvids:
        return "", []
    query = db.query(Item).filter(Item.status == "done")
    query = _apply_scope(query, folder_ids, bvids)
    rows = query.all()
    if not rows:
        return "", []

    blocks: list[str] = []
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        if not item.bvid:
            continue
        title = item.part_title or item.title
        summary = item.summary_json or {}
        overview = summary.get("overview", "")
        points = summary.get("points") or []
        parts = [f"《{title}》"]
        if overview:
            parts.append(f"概述：{overview}")
        if points:
            parts.append("要点：" + "；".join(str(p) for p in points))
        blocks.append("\n".join(parts))
        if item.bvid not in seen:
            seen.add(item.bvid)
            sources.append(
                {
                    "bvid": item.bvid,
                    "title": title,
                    "url": f"https://www.bilibili.com/video/{item.bvid}",
                    "snippet": _preview(overview, 200),
                }
            )
    return "\n\n".join(blocks), sources


# ------------------------------------------------------------------ 消息构建
def _build_direct_messages(question: str) -> list[dict[str, str]]:
    system = "你是一个知识库问答助手。\n请直接回答用户问题，避免引入知识库内容。"
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def _build_direct_messages_with_context(context: str, question: str) -> list[dict[str, str]]:
    system = (
        "你是一个知识库问答助手。\n"
        "以下是知识库的视频概览（标题与概述）：\n"
        f"{context}\n\n"
        "请先回答用户问题，再根据知识库内容引导用户提出与知识库相关的问题。"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def _build_db_list_messages(context: str, question: str) -> list[dict[str, str]]:
    system = (
        "你是一个知识库问答助手。\n"
        "用户需要清单/列表类答案，请基于以下视频标题与概述回答。\n"
        "回答要：\n1. 按主题分组\n2. 只输出与问题相关的条目\n3. 简洁清晰\n\n"
        f"知识库内容：\n{context}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def _build_db_summary_messages(context: str, question: str) -> list[dict[str, str]]:
    system = (
        "你是一个知识库问答助手。\n"
        "用户需要总结/提炼，请基于以下视频内容回答。\n"
        "回答要：\n1. 提炼重点与要点\n2. 结构清晰、可快速理解\n3. 必要时引用视频标题作为来源\n\n"
        f"知识库内容：\n{context}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def _build_rag_messages(context: str, question: str) -> list[dict[str, str]]:
    system = (
        "你是一个知识库助手，基于用户收藏的视频内容回答问题。\n"
        "请根据以下检索到的视频内容回答：\n"
        "1. 直接回答问题，引用相关内容\n"
        "2. 回答要自然、有条理\n"
        "3. 可以引用视频标题作为来源\n\n"
        f"相关内容：\n{context}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def _build_fallback_messages(context: str, question: str) -> list[dict[str, str]]:
    system = (
        "你是一个知识库问答助手。\n"
        "用户的问题在现有知识库中没有检索到直接内容。\n"
        "以下是知识库中的视频概览（如果为空说明用户还没入库）：\n"
        f"{context}\n\n"
        "请根据以上信息（如果有）：\n"
        "1. 尝试回答用户问题\n"
        "2. 如果没有任何视频信息，礼貌地告诉用户需要先入库\n"
        "3. 保持自然语气"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


# ------------------------------------------------------------------ 主流程
async def _prepare_messages(
    question: str,
    db: Any,
    settings: Settings,
    filter_dict: dict[str, Any] | None,
    progress_callback: ProgressCallback = None,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]]]:
    """准备 LLM 消息、来源与引用；返回 (messages, sources, citations)。"""
    question = question.strip()
    folder_ids: list[str] = []
    if filter_dict and filter_dict.get("folder_ids"):
        folder_ids = list(filter_dict["folder_ids"])
    bvids: list[str] = []
    if filter_dict and filter_dict.get("bvids"):
        bvids = list(filter_dict["bvids"])

    has_data = _has_done_items(db, folder_ids, bvids)
    is_collection_intent = _is_collection_intent(question)
    is_general = _is_general_question(question)
    if (folder_ids or bvids) and not is_general:
        is_collection_intent = True

    route: str | None = None
    if settings.chat_use_llm_router and not is_general:
        router_client = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
        route, _raw = await _route_with_llm(question, router_client)
    if not route:
        route = _route_with_rules(question, is_collection_intent, related=False)

    # 纯寒暄强制直接回答
    if is_general:
        route = "direct"

    _emit_progress(progress_callback, "route", route=route, label=_route_label(route))

    # 无已入库数据兜底
    if not has_data:
        if is_collection_intent:
            context, sources = _get_db_list_context(db, folder_ids, bvids, limit=50)
            if not context:
                context = "（暂无已入库的视频信息，请先入库）"
            return _build_fallback_messages(context, question), sources, []
        return _build_direct_messages(question), [], []

    # direct 纠偏：非寒暄问题若命中关键词则转入检索
    if route == "direct":
        if is_general:
            return _build_direct_messages(question), [], []
        if is_collection_intent:
            route = "vector"
            _emit_progress(progress_callback, "route", route=route, label=_route_label(route))
        else:
            related = await _is_related_to_collection(db, folder_ids, bvids, question)
            if related:
                route = "vector"
                _emit_progress(progress_callback, "route", route=route, label=_route_label(route))
            else:
                title_context, _ = _get_db_list_context(db, folder_ids, bvids, limit=50)
                messages = (
                    _build_direct_messages_with_context(title_context, question)
                    if title_context
                    else _build_direct_messages(question)
                )
                return messages, [], []

    if route == "direct":
        title_context, _ = _get_db_list_context(db, folder_ids, bvids, limit=50)
        messages = (
            _build_direct_messages_with_context(title_context, question)
            if title_context
            else _build_direct_messages(question)
        )
        return messages, [], []

    if route == "db_list":
        if not is_collection_intent:
            related = await _is_related_to_collection(db, folder_ids, bvids, question)
            if not related:
                return _build_direct_messages(question), [], []
        context, sources = _get_db_list_context(db, folder_ids, bvids, limit=50)
        if not context:
            return _build_fallback_messages("（暂无信息，请入库）", question), sources, []
        return _build_db_list_messages(context, question), sources, []

    if route == "db_content":
        if not is_collection_intent:
            related = await _is_related_to_collection(db, folder_ids, bvids, question)
            if not related:
                return _build_direct_messages(question), [], []
        context, sources = _get_db_content_context(db, folder_ids, bvids)
        if not context:
            return _build_fallback_messages("（暂无信息，请入库）", question), sources, []
        return _build_db_summary_messages(context, question), sources, []

    # vector：混合检索
    recall_started = time.perf_counter()
    docs, vector_count, keyword_count = await _retrieve(
        settings, question, db, folder_ids, bvids, filter_dict
    )
    _emit_progress(
        progress_callback,
        "retrieval",
        vector_count=vector_count,
        keyword_count=keyword_count,
        final_count=len(docs),
        elapsed_ms=round((time.perf_counter() - recall_started) * 1000),
    )

    if docs:
        context_parts: list[str] = []
        sources: list[dict[str, Any]] = []
        seen: set[str] = set()
        for doc in docs:
            title = _doc_title(db, doc)
            content = (doc.page_content or "").strip()
            if content:
                context_parts.append(f"【{title}】\n{content}")
            meta = doc.metadata or {}
            bvid = meta.get("bvid", "")
            if bvid and bvid not in seen:
                seen.add(bvid)
                sources.append(
                    {
                        "bvid": bvid,
                        "title": title,
                        "url": meta.get("url") or f"https://www.bilibili.com/video/{bvid}",
                        "snippet": _preview(content),
                    }
                )
        citations = _build_citations(docs, db)
        return (
            _build_rag_messages("\n\n---\n\n".join(context_parts), question),
            sources,
            citations,
        )

    # 检索空结果兜底
    context, sources = _get_db_list_context(db, folder_ids, bvids, limit=50)
    return _build_fallback_messages(context or "（暂无入库信息）", question), sources, []


def _load_history(db: Any, session_id: str, limit: int = 10) -> list[dict[str, str]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def _with_history(
    messages: list[dict[str, str]], history: list[dict[str, str]]
) -> list[dict[str, str]]:
    """把多轮历史插到系统提示与当前问题之间。"""
    if not messages:
        return list(history)
    return [messages[0]] + list(history) + messages[1:]


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

    history = _load_history(db, session.id)
    session_id = session.id

    async def gen() -> AsyncIterator[str]:
        collected: list[str] = []
        progress_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def report(event: dict[str, Any]) -> None:
            progress_queue.put_nowait(event)

        try:
            with get_session_factory()() as db_session:
                prepare_task = asyncio.create_task(
                    _prepare_messages(
                        req.question, db_session, settings, req.filter, progress_callback=report
                    )
                )
                while not prepare_task.done():
                    try:
                        event = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                        yield _sse(event)
                    except TimeoutError:
                        continue
                while not progress_queue.empty():
                    yield _sse(progress_queue.get_nowait())
                messages, sources, citations = await prepare_task

            yield _sse({"type": "sources", "items": sources[:5]})

            client = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
            async for piece in client.stream_complete(_with_history(messages, history)):
                collected.append(piece)
                yield _sse({"type": "delta", "content": piece})
            answer = "".join(collected)
            _save_assistant(session_id, answer, citations)
            yield _sse({"type": "done", "session_id": session_id, "citations": citations})
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
