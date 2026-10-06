"""链接导入（§7.3）。"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..models import Folder
from ..services.bilibili import BilibiliClient
from ..services.bilibili.session import load_cookies
from ..services.items import create_items
from .deps import get_db

router = APIRouter(prefix="/api", tags=["import"])

_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")


class ParseRequest(BaseModel):
    links: list[str]


class ConfirmRequest(BaseModel):
    targets: list[dict[str, Any]]
    folder_id: str | None = None


def _extract_bvid(link: str) -> str | None:
    match = _BV_RE.search(link)
    return match.group(1) if match else None


@router.post("/import/parse")
async def parse_links(req: ParseRequest, db: Any = Depends(get_db)) -> list[dict[str, Any]]:
    client = BilibiliClient(cookies=load_cookies(db))
    results: list[dict[str, Any]] = []
    for link in req.links:
        bvid = _extract_bvid(link.strip())
        if bvid is None:
            results.append({"link": link, "error": "无法识别 BV 号"})
            continue
        try:
            info = await client.get_video_info(bvid)
            results.append({"link": link, **info})
        except Exception as exc:  # noqa: BLE001
            results.append({"link": link, "bvid": bvid, "error": str(exc)})
    return results


@router.post("/import/confirm")
async def confirm_import(
    req: ConfirmRequest, request: Request, db: Any = Depends(get_db)
) -> dict[str, Any]:
    if req.folder_id:
        folder = db.get(Folder, req.folder_id)
    else:
        folder = db.query(Folder).filter(Folder.kind == "uncategorized").first()

    targets = [{**t, "folder_id": folder.id if folder else None} for t in req.targets]
    batch_id = str(uuid4())
    created = create_items(db, targets, source_type="link", batch_id=batch_id)

    queue = getattr(request.app.state, "task_queue", None)
    item_ids = [item.id for item in created]
    if queue is not None:
        queue.enqueue_many(item_ids)

    return {"created": len(created), "item_ids": item_ids, "batch_id": batch_id}
