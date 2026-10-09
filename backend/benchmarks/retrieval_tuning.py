"""RRF 权重扫描：验证「向量 1.0 > 关键词 0.9」是否压制了仅关键词命中的正确结果。

只读评测：对同一批查询缓存好向量/关键词两通道结果，仅改变 `merge_ranked_documents`
的 channel_weights 重新融合，找出让混合检索 recall 最大化的权重。不修改生产代码。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from app.api.chat import _keyword_search_docs  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models import Item  # noqa: E402
from app.services.indexing import Embedder, VectorStore  # noqa: E402
from app.services.retrieval import (  # noqa: E402
    RETRIEVAL_CANDIDATE_K,
    RETRIEVAL_MMR_FETCH_K,
    RETRIEVAL_MMR_LAMBDA,
    merge_ranked_documents,
)


def recall_at(docs, target, k):
    return target in [d.metadata.get("bvid") for d in docs[:k]]


def pct(vals):
    return f"{100 * sum(vals) / len(vals):.0f}%" if vals else "n/a"


async def main() -> None:
    session = get_session_factory()()
    settings = load_settings(session)
    top_k = settings.top_k

    items = session.query(Item).filter(Item.status == "done").all()
    embedder = Embedder(
        model_name=settings.embedding_model,
        provider=settings.embedding_provider,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
    store = VectorStore(path=settings.chroma_path, embedder=embedder)
    embedder.embed(["预热"])

    queries: list[tuple[str, str, str]] = []  # (bvid, text, kind)
    for it in items:
        t = (it.part_title or it.title or "").strip()
        if t:
            queries.append((it.bvid, t, "title"))
        ov = ((it.summary_json or {}).get("overview") or "").strip()
        if ov:
            queries.append((it.bvid, ov, "overview"))

    cache = []
    for target, q, kind in queries:
        vdocs = store.search_mmr(q, top_k, RETRIEVAL_MMR_FETCH_K, RETRIEVAL_MMR_LAMBDA, None)
        kdocs = await _keyword_search_docs(session, None, None, q, RETRIEVAL_CANDIDATE_K, None)
        cache.append((target, kind, vdocs, kdocs))

    configs = [
        ("当前(1.0/0.9)", {"vector": 1.0, "keyword": 0.9}),
        ("调平(1.0/1.0)", {"vector": 1.0, "keyword": 1.0}),
        ("关键词1.1", {"vector": 1.0, "keyword": 1.1}),
        ("关键词1.2", {"vector": 1.0, "keyword": 1.2}),
        ("向量1.1", {"vector": 1.1, "keyword": 1.0}),
    ]

    print("=" * 70)
    print(f"RRF 权重扫描（查询 {len(queries)} 条，top_k={top_k}）")
    print("=" * 70)
    print(f"{'权重配置':<16}{'总体@1':>8}{'总体@3':>8}{'总体@5':>8}{'标题@5':>8}{'概述@5':>8}")
    for label, cw in configs:
        all1, all3, all5, t5, o5 = [], [], [], [], []
        for target, kind, vdocs, kdocs in cache:
            docs = merge_ranked_documents(
                {"vector": vdocs, "keyword": kdocs},
                top_k=top_k,
                channel_weights=cw,
                per_video_limit=2,
            )
            all1.append(recall_at(docs, target, 1))
            all3.append(recall_at(docs, target, 3))
            all5.append(recall_at(docs, target, 5))
            (t5 if kind == "title" else o5).append(recall_at(docs, target, 5))
        print(
            f"{label:<16}"
            f"{pct(all1):>8}{pct(all3):>8}{pct(all5):>8}{pct(t5):>8}{pct(o5):>8}"
        )

    session.close()


if __name__ == "__main__":
    asyncio.run(main())
