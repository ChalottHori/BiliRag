"""收藏夹浏览与同步（§7.2）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..models import Folder, Item
from ..schemas import FolderRead
from ..services.bilibili import BilibiliClient
from ..services.bilibili.session import load_cookies
from .deps import get_db

router = APIRouter(prefix="/api", tags=["folders"])


def _parts_status(db: Any, bvids: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    """按 bvid 聚合各分P（cid）的入库状态，供前端标注「已入库 / 失败重试」。"""
    if not bvids:
        return {}
    rows = db.query(Item).filter(Item.bvid.in_(bvids)).all()
    by_bvid: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_bvid.setdefault(row.bvid, {})[str(row.cid)] = {
            "item_id": row.id,
            "status": row.status,
            "error_msg": row.error_msg,
        }
    return by_bvid


def _enrich_videos(db: Any, videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    status_by_bvid = _parts_status(db, [v.get("bvid", "") for v in videos if v.get("bvid")])
    for video in videos:
        video["parts_status"] = status_by_bvid.get(video.get("bvid", ""), {})
    return videos


@router.get("/folders")
def list_folders(db: Any = Depends(get_db)) -> list[dict[str, Any]]:
    folders = db.query(Folder).order_by(Folder.title).all()
    return [FolderRead.model_validate(f).model_dump() for f in folders]


@router.post("/folders/sync")
async def sync_folders(db: Any = Depends(get_db)) -> dict[str, Any]:
    client = BilibiliClient(cookies=load_cookies(db))
    nav = await client.get_nav()
    mid = str(nav.get("mid", ""))
    if not mid:
        raise HTTPException(status_code=401, detail="未登录")

    remote = await client.get_folders(mid)
    for item in remote:
        existing = db.query(Folder).filter(Folder.fid == item["fid"]).first()
        if existing is None:
            existing = Folder(
                fid=item["fid"],
                title=item["title"],
                kind="bilibili",
                media_count=item["media_count"],
            )
            db.add(existing)
        else:
            existing.title = item["title"]
            existing.media_count = item["media_count"]
    db.commit()
    return {"count": len(remote)}


@router.get("/folders/{folder_id}/videos")
async def list_folder_videos(
    folder_id: str,
    page: int = 1,
    page_size: int = 20,
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="folder not found")

    # 「未分类」是本地虚拟目录，没有 B 站 fid，直接返回空列表
    if folder.fid is None:
        return {"items": [], "total": 0}

    client = BilibiliClient(cookies=load_cookies(db))
    if folder.is_watch_later:
        videos = await client.get_watch_later()
        return {"items": _enrich_videos(db, videos), "total": len(videos)}
    result = await client.get_folder_videos(folder.fid, page=page, page_size=page_size)
    return {"items": _enrich_videos(db, result["videos"]), "total": result["total"]}


@router.get("/videos/{bvid}/parts")
async def list_video_parts(bvid: str, db: Any = Depends(get_db)) -> list[dict[str, Any]]:
    client = BilibiliClient(cookies=load_cookies(db))
    parts = await client.get_video_parts(bvid)
    status_by_cid = _parts_status(db, [bvid]).get(bvid, {})
    for part in parts:
        part["item_status"] = status_by_cid.get(str(part.get("cid", 0)))
    return parts
