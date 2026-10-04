"""知识库 / 管理（§7.5）：组合查询、详情、删除、本地归类。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..config import load_settings
from ..models import Item
from ..schemas import ItemRead
from ..services.indexing import VectorStore
from .deps import get_db

router = APIRouter(prefix="/api", tags=["items"])


class MoveRequest(BaseModel):
    ids: list[str]
    folder_id: str | None = None


@router.get("/items")
def list_items(
    folder_id: str | None = None,
    keyword: str | None = None,
    time_from: datetime | None = None,
    time_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    query = db.query(Item)
    if folder_id:
        query = query.filter(Item.folder_id == folder_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            Item.title.like(like) | Item.part_title.like(like) | Item.transcript.like(like)
        )
    if time_from:
        query = query.filter(Item.imported_at >= time_from)
    if time_to:
        query = query.filter(Item.imported_at <= time_to)

    total = query.count()
    rows = (
        query.order_by(Item.imported_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "items": [ItemRead.model_validate(r).model_dump() for r in rows],
    }


@router.get("/items/{item_id}")
def get_item(item_id: str, db: Any = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    data = ItemRead.model_validate(item).model_dump()
    data["summary"] = item.summary_json
    data["transcript_snippet"] = (item.transcript or "")[:2000]
    return data


@router.post("/items/move")
def move_items(req: MoveRequest, db: Any = Depends(get_db)) -> dict[str, str]:
    for item_id in req.ids:
        item = db.get(Item, item_id)
        if item is not None:
            item.folder_id = req.folder_id
    db.commit()
    return {"status": "ok"}


@router.delete("/items/{item_id}")
def delete_item(item_id: str, db: Any = Depends(get_db)) -> dict[str, str]:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    settings = load_settings(db)
    VectorStore(path=settings.chroma_path).delete(item_id)
    db.delete(item)
    db.commit()
    return {"status": "ok"}
