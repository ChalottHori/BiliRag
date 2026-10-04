"""收藏夹浏览与同步（§7.2）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..models import Folder
from ..schemas import FolderRead
from ..services.bilibili import BilibiliClient
from ..services.bilibili.session import load_cookies
from .deps import get_db

router = APIRouter(prefix="/api", tags=["folders"])


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


@router.get("/folders/{fid}/videos")
async def list_folder_videos(
    fid: str,
    page: int = 1,
    page_size: int = 20,
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    client = BilibiliClient(cookies=load_cookies(db))
    if fid == "watch_later":
        videos = await client.get_watch_later()
        return {"items": videos, "total": len(videos)}
    result = await client.get_folder_videos(fid, page=page, page_size=page_size)
    return {"items": result["videos"], "total": result["total"]}


@router.get("/videos/{bvid}/parts")
async def list_video_parts(bvid: str, db: Any = Depends(get_db)) -> list[dict[str, Any]]:
    client = BilibiliClient(cookies=load_cookies(db))
    return await client.get_video_parts(bvid)
