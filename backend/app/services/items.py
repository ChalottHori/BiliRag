"""条目创建（`(bvid, cid)` 去重）与相关查询。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import Item, Part, Video


def _to_datetime(pubdate: Any) -> datetime | None:
    if not pubdate:
        return None
    try:
        return datetime.fromtimestamp(int(pubdate))
    except (TypeError, ValueError, OSError):
        return None


def create_items(
    session: Any, targets: list[dict[str, Any]], source_type: str = "folder"
) -> list[Item]:
    """按 target 创建 Video/Part/Item（`(bvid, cid)` 去重，重复跳过）。"""
    created: list[Item] = []
    for target in targets:
        bvid = str(target.get("bvid", "")).strip()
        cid = int(target.get("cid", 0))
        if not bvid or not cid:
            continue

        existing = session.query(Item).filter(Item.bvid == bvid, Item.cid == cid).first()
        if existing is not None:
            continue  # 去重跳过

        video = session.query(Video).filter(Video.bvid == bvid).first()
        if video is None:
            video = Video(
                bvid=bvid,
                aid=int(target.get("aid", 0)),
                title=target.get("title", ""),
                cover_url=target.get("cover_url", ""),
                up_name=target.get("up_name", ""),
                pubdate=_to_datetime(target.get("pubdate")),
                duration=int(target.get("duration", 0)),
                is_collection=bool(target.get("is_collection", False)),
                is_invalid=bool(target.get("is_invalid", False)),
            )
            session.add(video)
            session.flush()

        part = session.query(Part).filter(Part.video_id == video.id, Part.cid == cid).first()
        if part is None:
            part = Part(
                video_id=video.id,
                cid=cid,
                page=int(target.get("page", 1)),
                part_title=target.get("part_title", ""),
                duration=int(target.get("duration", 0)),
            )
            session.add(part)
            session.flush()

        item = Item(
            video_id=video.id,
            part_id=part.id,
            bvid=bvid,
            aid=int(target.get("aid", 0)),
            cid=cid,
            title=target.get("title", ""),
            part_title=target.get("part_title", ""),
            cover_url=target.get("cover_url", ""),
            up_name=target.get("up_name", ""),
            pubdate=_to_datetime(target.get("pubdate")),
            duration=int(target.get("duration", 0)),
            source_type=source_type,
            folder_id=target.get("folder_id"),
        )
        session.add(item)
        created.append(item)

    session.commit()
    return created
