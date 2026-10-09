"""实测：混合检索 vs 纯向量 vs 纯关键词 的 recall@k 与检索耗时。

自监督评测：以每个已入库视频的「标题 / 结构化概述」作为查询，
命中目标视频（bvid 出现在 top-k 结果中）即算召回成功。
全程本地运行（embedding 用已缓存的 bge-small-zh-v1.5），不调用 LLM。

复用项目真实代码：`Embedder` / `VectorStore` / `_keyword_search_docs` /
`merge_ranked_documents`（RRF），参数取模块常量与 settings.top_k。
"""
from __future__ import annotations

import asyncio
import statistics
import sys
import time
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

METHODS = ("hybrid", "vector", "keyword")
KS = (1, 3, 5)


def bvids_of(docs):
    return [d.metadata.get("bvid") for d in docs]


def recall_at(docs, target, k):
    return target in bvids_of(docs[:k])


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

    # 预热：首次加载 embedding 模型不计入耗时
    embedder.embed(["预热"])

    probe = store.search_mmr("测试", 3, RETRIEVAL_MMR_FETCH_K, RETRIEVAL_MMR_LAMBDA, None)
    print(f"[自检] 向量库可检索，probe 返回 {len(probe)} 条；done 条目 {len(items)} 条\n")

    # 构建查询：标题（测精确/关键词）+ 概述（测语义/向量）
    queries: list[tuple[str, str, str]] = []  # (target_bvid, text, kind)
    for it in items:
        t = (it.part_title or it.title or "").strip()
        if t:
            queries.append((it.bvid, t, "title"))
        ov = ((it.summary_json or {}).get("overview") or "").strip()
        if ov:
            queries.append((it.bvid, ov, "overview"))

    recall = {m: {k: [] for k in KS} for m in METHODS}  # 每个 query 一个布尔
    kind_of_query: list[str] = []
    lat_ms = {m: [] for m in METHODS}
    diversity = {m: [] for m in METHODS}

    for target, qtext, kind in queries:
        kind_of_query.append(kind)

        # 向量通道（embedding + MMR）
        t0 = time.perf_counter()
        vdocs = await asyncio.to_thread(
            store.search_mmr, qtext, top_k, RETRIEVAL_MMR_FETCH_K, RETRIEVAL_MMR_LAMBDA, None
        )
        lat_ms["vector"].append((time.perf_counter() - t0) * 1000)

        # 关键词通道（SQLite 加权）
        t0 = time.perf_counter()
        kdocs = await _keyword_search_docs(session, None, None, qtext, RETRIEVAL_CANDIDATE_K, None)
        lat_ms["keyword"].append((time.perf_counter() - t0) * 1000)

        # 混合（RRF 融合；双通道并发端到端 ≈ max(向量, 关键词) + 融合）
        t0 = time.perf_counter()
        hdocs = merge_ranked_documents(
            {"vector": vdocs, "keyword": kdocs},
            top_k=top_k,
            channel_weights={"vector": 1.0, "keyword": 1.0},
            per_video_limit=2,
        )
        merge_ms = (time.perf_counter() - t0) * 1000
        lat_ms["hybrid"].append(max(lat_ms["vector"][-1], lat_ms["keyword"][-1]) + merge_ms)

        for m, docs in (("hybrid", hdocs), ("vector", vdocs), ("keyword", kdocs)):
            for k in KS:
                recall[m][k].append(recall_at(docs, target, k))
            diversity[m].append(len({b for b in bvids_of(docs[:top_k]) if b}))

    # ---------------- 输出 ----------------
    title_idx = [i for i, k in enumerate(kind_of_query) if k == "title"]
    ov_idx = [i for i, k in enumerate(kind_of_query) if k == "overview"]
    all_idx = list(range(len(kind_of_query)))

    print("=" * 64)
    print(f"recall@k 实测（查询 {len(queries)} 条：标题 {len(title_idx)} + 概述 {len(ov_idx)}，top_k={top_k}）")
    print("=" * 64)
    for label, idx in (("总体", all_idx), ("标题类查询", title_idx), ("概述类查询", ov_idx)):
        print(f"\n{label}：")
        print(f"{'k':>4}{'混合':>10}{'纯向量':>10}{'纯关键词':>10}")
        for k in KS:
            print(
                f"{k:>4}"
                f"{pct([recall['hybrid'][k][i] for i in idx]):>10}"
                f"{pct([recall['vector'][k][i] for i in idx]):>10}"
                f"{pct([recall['keyword'][k][i] for i in idx]):>10}"
            )

    print("\n" + "=" * 64)
    print("检索耗时（稳态，embedding 模型已预热）")
    print("=" * 64)
    for m in METHODS:
        v = sorted(lat_ms[m])
        mean = statistics.fmean(v)
        med = statistics.median(v)
        p95 = v[int(len(v) * 0.95) - 1] if len(v) >= 20 else v[-1]
        print(f"  {m:>8}: 平均 {mean:6.0f} ms / 中位 {med:6.0f} ms / 最大 {max(v):6.0f} ms")

    print("\n" + "=" * 64)
    print(f"结果多样性（top-{top_k} 中不同视频数）")
    print("=" * 64)
    for m in METHODS:
        print(f"  {m:>8}: 平均 {statistics.fmean(diversity[m]):.1f} 个不同视频")

    session.close()


if __name__ == "__main__":
    asyncio.run(main())
