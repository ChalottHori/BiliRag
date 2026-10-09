"""实测：db_content 路由用结构化摘要(summary_json)替代全文稿(transcript)的上下文压缩比。

只读访问 app.db，不调用任何外部服务（LLM/embedding/网络）。
summary_text() 复刻 `app/api/chat.py::_get_db_content_context` 的拼接逻辑
（标题 + 概述 + 要点），因此所得压缩比即该路由真实省下的上下文。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from app.db import get_session_factory  # noqa: E402
from app.models import Item  # noqa: E402


def summary_text(item: Item) -> str:
    """复刻 db_content 路由的上下文拼接（《标题》+ 概述 + 要点）。"""
    s = item.summary_json or {}
    parts = [item.part_title or item.title or ""]
    overview = (s.get("overview") or "").strip()
    if overview:
        parts.append(f"概述：{overview}")
    points = s.get("points") or []
    if points:
        parts.append("要点：" + "；".join(str(p) for p in points))
    return "\n".join(p for p in parts if p)


def main() -> None:
    with get_session_factory()() as session:
        items = session.query(Item).filter(Item.status == "done").all()

    total_transcript = sum(len((i.transcript or "").strip()) for i in items)
    total_summary = sum(len(summary_text(i).strip()) for i in items)

    ratios = []
    for i in items:
        t = len((i.transcript or "").strip())
        s = len(summary_text(i).strip())
        if t > 0 and s > 0:
            ratios.append(t / s)
    ratios.sort()

    n = len(items)
    print("=" * 60)
    print("token 压缩比实测（db_content 路由：摘要 vs 全文稿）")
    print("=" * 60)
    print(f"已入库(done)条目数        : {n}")
    print(f"全文稿(transcript)总字符  : {total_transcript}")
    print(f"结构化摘要(summary)总字符 : {total_summary}")
    print(f"整体压缩比                : 1 : {total_transcript / total_summary:.1f}")
    print(f"  即上下文缩小            : {100 * (1 - total_summary / total_transcript):.1f}%")
    print("-" * 60)
    print("单条目压缩比分布（transcript / summary）:")
    print(f"  平均 1 : {sum(ratios) / len(ratios):.1f}")
    print(f"  中位 1 : {ratios[len(ratios) // 2]:.1f}")
    print(f"  最小 1 : {ratios[0]:.1f}")
    print(f"  最大 1 : {ratios[-1]:.1f}")
    print("-" * 60)
    print("注：中文约 1 字符 ≈ 1 token，字符比可直接作为 token 比的估算。")


if __name__ == "__main__":
    main()
