"""检索纯函数：关键词抽取 / 字段打分 / 摘要截断 / 文档去重键 / RRF 融合。

保持零重依赖（不 import chromadb / sentence-transformers / LLM 客户端 / httpx），
便于在不初始化向量库、嵌入模型或外部客户端的环境下单测排序逻辑。
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

# 检索参数（方案 §3.6：写死为模块常量，不作为用户配置暴露）。
RETRIEVAL_CANDIDATE_K = 24
RETRIEVAL_MMR_FETCH_K = 32
RETRIEVAL_MMR_LAMBDA = 0.55

_STOPWORDS = {
    "什么",
    "怎么",
    "如何",
    "是否",
    "可以",
    "哪个",
    "哪些",
    "请问",
    "一下",
    "为什么",
    "有没有",
    "能不能",
    "能否",
    "是不是",
    "是什么",
    "多少",
    "哪里",
    "讲讲",
    "介绍",
    "总结",
    "概括",
    "分析",
    "解释",
    "说明",
    "评价",
    "区别",
    "内容",
    "视频",
    "收藏",
    "收藏夹",
    "知识库",
    "这个",
    "那个",
    "里面",
    "相关",
    "关于",
    "一下子",
}


def extract_keywords(text: str, max_keywords: int = 16) -> list[str]:
    """抽取召回导向的关键词：去停用词 + 英文 token + 中文 n-gram（2–4），无 jieba。"""
    if not text:
        return []

    cleaned = text.strip()
    for stopword in sorted(_STOPWORDS, key=len, reverse=True):
        cleaned = cleaned.replace(stopword, " ")

    keywords: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        token = token.strip()
        if len(token) < 2 or token in _STOPWORDS or token in seen:
            return
        seen.add(token)
        keywords.append(token)

    for token in re.findall(r"[A-Za-z][A-Za-z0-9_+.#-]{1,}|[0-9]{2,}", cleaned):
        add(token)

    for chunk in re.findall(r"[一-鿿]{2,}", cleaned):
        add(chunk)
        # 中文常连成一片，补充 2–4 字 n-gram，使关键词通道无需 jieba 也能命中标题/正文。
        if len(chunk) > 4:
            for size in (4, 3, 2):
                for idx in range(0, len(chunk) - size + 1):
                    add(chunk[idx : idx + size])
                    if len(keywords) >= max_keywords:
                        return keywords
        if len(keywords) >= max_keywords:
            return keywords

    return keywords[:max_keywords]


def keyword_score(
    keywords: Sequence[str],
    *,
    title: str = "",
    content: str = "",
    owner_name: str = "",
) -> float:
    """按字段加权给关键词召回打分：标题(8.0) > UP主(5.0) > 正文(1.0)，无简介档。"""
    if not keywords:
        return 0.0

    score = 0.0
    fields = (
        (title or "", 8.0),
        (owner_name or "", 5.0),
        (content or "", 1.0),
    )

    for keyword in keywords:
        weight = min(max(len(keyword), 2), 8)
        is_ascii = re.search(r"[A-Za-z]", keyword) is not None
        keyword_lower = keyword.lower()
        for value, field_weight in fields:
            if not value:
                continue
            haystack = value.lower() if is_ascii else value
            needle = keyword_lower if is_ascii else keyword
            count = haystack.count(needle)
            if count:
                score += count * field_weight * weight
    return score


def build_snippet(text: str, keywords: Sequence[str], max_length: int = 700) -> str:
    """围绕首个关键词命中截断出紧凑摘要。"""
    value = (text or "").strip()
    if len(value) <= max_length:
        return value

    first_hit = -1
    for keyword in keywords:
        if re.search(r"[A-Za-z]", keyword):
            idx = value.lower().find(keyword.lower())
        else:
            idx = value.find(keyword)
        if idx >= 0 and (first_hit < 0 or idx < first_hit):
            first_hit = idx

    if first_hit < 0:
        return value[:max_length].rstrip() + "..."

    start = max(0, first_hit - max_length // 3)
    end = min(len(value), start + max_length)
    snippet = value[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(value):
        snippet += "..."
    return snippet


def _metadata(doc: Any) -> dict:
    meta = getattr(doc, "metadata", None)
    return meta if isinstance(meta, dict) else {}


def document_identity(doc: Any) -> str:
    """跨检索通道的稳定去重键：优先 `item_id:doc_type:chunk_idx`，无 item_id 回退 `id(doc)`。"""
    meta = _metadata(doc)
    item_id = meta.get("item_id")
    if item_id:
        doc_type = meta.get("doc_type", "chunk")
        chunk_idx = meta.get("chunk_idx", meta.get("chunk_index", ""))
        return f"{item_id}:{doc_type}:{chunk_idx}"
    return str(id(doc))


def merge_ranked_documents(
    rankings: Mapping[str, Sequence[Any]],
    *,
    top_k: int,
    channel_weights: Mapping[str, float] | None = None,
    rank_constant: int = 60,
    per_video_limit: int = 2,
) -> list[Any]:
    """用 RRF 融合多个排序列表，并按 bvid 保持来源多样性（deferred 补位兜底）。"""
    if top_k <= 0:
        return []

    weights = channel_weights or {}
    scores: dict[str, float] = defaultdict(float)
    docs_by_key: dict[str, Any] = {}
    best_rank: dict[str, int] = {}

    for channel, docs in rankings.items():
        weight = weights.get(channel, 1.0)
        for rank, doc in enumerate(docs, start=1):
            key = document_identity(doc)
            docs_by_key.setdefault(key, doc)
            scores[key] += weight / (rank_constant + rank)
            best_rank[key] = min(best_rank.get(key, rank), rank)

    ordered_keys = sorted(
        docs_by_key,
        key=lambda key: (-scores[key], best_rank.get(key, 10_000), key),
    )

    results: list[Any] = []
    per_video_counts: dict[str, int] = defaultdict(int)
    deferred: list[str] = []

    for key in ordered_keys:
        doc = docs_by_key[key]
        bvid = _metadata(doc).get("bvid")
        if bvid and per_video_counts[bvid] >= per_video_limit:
            deferred.append(key)
            continue
        results.append(doc)
        if bvid:
            per_video_counts[bvid] += 1
        if len(results) >= top_k:
            break

    if len(results) < top_k:
        existing = {document_identity(doc) for doc in results}
        for key in deferred:
            if key in existing:
                continue
            results.append(docs_by_key[key])
            if len(results) >= top_k:
                break

    for doc in results:
        meta = _metadata(doc)
        if meta:
            meta["retrieval_score"] = round(scores[document_identity(doc)], 6)

    return results
