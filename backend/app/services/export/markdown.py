"""Markdown 生成。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...models import ChatMessage, ChatSession, Folder, Item


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return cleaned or "untitled"


def _fmt_date(value: Any) -> str:
    return value.strftime("%Y-%m-%d") if value is not None else ""


def build_item_markdown(item: Item) -> str:
    title = item.part_title or item.title
    summary = item.summary_json or {}

    lines = [f"# {title}", ""]
    lines.append(f"- **BV 号**：{item.bvid}")
    lines.append(f"- **链接**：https://www.bilibili.com/video/{item.bvid}")
    if item.pubdate:
        lines.append(f"- **发布时间**：{_fmt_date(item.pubdate)}")
    lines.append("")

    if summary.get("overview"):
        lines += ["## 概述", "", str(summary["overview"]), ""]

    points = summary.get("points") or []
    if points:
        lines += ["## 要点", ""]
        lines += [f"- {p}" for p in points]
        lines.append("")

    keywords = summary.get("keywords") or []
    if keywords:
        lines += ["## 关键词", "", "、".join(str(k) for k in keywords), ""]

    return "\n".join(lines)


def export_items_markdown(
    session: Any,
    settings: Any,
    item_ids: list[str] | None = None,
    folder_ids: list[str] | None = None,
    export_all: bool = False,
    dest_dir: str | None = None,
) -> dict[str, Any]:
    """导出已完成条目为 Markdown：按收藏夹分目录 + 总索引。"""
    query = session.query(Item).filter(Item.status == "done")
    if export_all:
        pass
    elif item_ids:
        query = query.filter(Item.id.in_(item_ids))
    elif folder_ids:
        query = query.filter(Item.folder_id.in_(folder_ids))
    else:
        query = query.filter(Item.id.in_([]))
    items = query.all()

    dest = Path(dest_dir or settings.exports_path)
    dest.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[Item]] = {}
    for item in items:
        folder_name = "未分类"
        if item.folder_id:
            folder = session.get(Folder, item.folder_id)
            if folder is not None:
                folder_name = _safe_filename(folder.title)
        grouped.setdefault(folder_name, []).append(item)

    files: list[str] = []
    index_lines = ["# BiliRag 导出索引", ""]
    for folder_name, folder_items in sorted(grouped.items()):
        subdir = dest / folder_name
        subdir.mkdir(parents=True, exist_ok=True)
        index_lines.append(f"## {folder_name}")
        for item in folder_items:
            name = _safe_filename(item.part_title or item.title) + ".md"
            path = subdir / name
            path.write_text(build_item_markdown(item), encoding="utf-8")
            files.append(str(path))
            index_lines.append(f"- [{item.part_title or item.title}]({folder_name}/{name})")
        index_lines.append("")

    index_path = dest / "index.md"
    index_path.write_text("\n".join(index_lines), encoding="utf-8")
    files.append(str(index_path))

    return {"count": len(items), "dest_dir": str(dest), "files": files}


def build_session_markdown(chat_session: ChatSession, messages: list[ChatMessage]) -> str:
    lines = [f"# {chat_session.title or '对话'}", ""]
    for message in messages:
        role = "用户" if message.role == "user" else "助手"
        ts = message.created_at.strftime("%Y-%m-%d %H:%M") if message.created_at else ""
        lines.append(f"**{role}**（{ts}）")
        lines.append("")
        lines.append(message.content)
        lines.append("")
        citations = message.citations_json or []
        if citations:
            lines.append("出处：")
            for citation in citations:
                lines.append(f"- {citation.get('title', '')}（{citation.get('bvid', '')}）")
            lines.append("")
    return "\n".join(lines)
