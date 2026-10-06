"""总结任务（§7.4）：批量创建条目并入队、进度、重试、重新总结、合集总摘要。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..config import load_settings
from ..models import CollectionSummary, Item
from ..services.items import create_items
from ..services.llm import LLMClient
from ..services.llm import summarize as llm_summarize
from .deps import get_db

router = APIRouter(prefix="/api", tags=["summarize"])


class SummarizeRequest(BaseModel):
    targets: list[dict[str, Any]]
    source_type: str = "folder"
    folder_id: str | None = None


@router.post("/summarize")
def summarize(req: SummarizeRequest, request: Request, db: Any = Depends(get_db)) -> dict[str, Any]:
    targets = [{**t, "folder_id": t.get("folder_id") or req.folder_id} for t in req.targets]
    batch_id = str(uuid4())
    created = create_items(db, targets, source_type=req.source_type, batch_id=batch_id)

    queue = getattr(request.app.state, "task_queue", None)
    item_ids = [item.id for item in created]
    if queue is not None:
        queue.enqueue_many(item_ids)
    return {"created": len(created), "item_ids": item_ids, "batch_id": batch_id}


_NEEDS_ATTENTION = ("pending", "transcribing", "summarizing", "failed")


def _empty_tasks() -> dict[str, Any]:
    return {"batch_id": None, "total": 0, "done": 0, "failed": 0, "active": 0, "items": []}


@router.get("/tasks")
def tasks(db: Any = Depends(get_db)) -> dict[str, Any]:
    """返回「最近一个需关注批次」的快照（以 item 表为准，刷新/重启后仍正确）。

    需关注批次 = 仍含非终态或失败条目、且 imported_at 最新的批次；无则返回空。
    """
    rows = db.query(Item).filter(Item.batch_id.isnot(None)).all()
    if not rows:
        return _empty_tasks()

    batches: dict[str, dict[str, Any]] = {}
    for row in rows:
        batch = batches.setdefault(
            row.batch_id, {"batch_id": row.batch_id, "latest": None, "items": []}
        )
        batch["items"].append(row)
        if batch["latest"] is None or (row.imported_at and row.imported_at > batch["latest"]):
            batch["latest"] = row.imported_at

    attention: dict[str, Any] | None = None
    for batch in batches.values():
        if any(item.status in _NEEDS_ATTENTION for item in batch["items"]):
            if attention is None or batch["latest"] > attention["latest"]:
                attention = batch

    if attention is None:
        return _empty_tasks()

    items: list[Item] = attention["items"]
    total = len(items)
    done = sum(1 for it in items if it.status == "done")
    failed = sum(1 for it in items if it.status == "failed")
    active = total - done - failed
    return {
        "batch_id": attention["batch_id"],
        "total": total,
        "done": done,
        "failed": failed,
        "active": active,
        "items": [
            {
                "item_id": it.id,
                "title": it.title,
                "part_title": it.part_title,
                "status": it.status,
                "error_msg": it.error_msg,
            }
            for it in items
        ],
    }


@router.post("/items/{item_id}/retry")
def retry(item_id: str, request: Request, db: Any = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    # 历史数据可能没有 batch_id，重试时补一个，确保进度面板可追踪
    if not item.batch_id:
        item.batch_id = str(uuid4())
    # transcript 已存则跳过转写
    item.status = "summarizing" if item.transcript else "pending"
    item.error_msg = ""
    db.commit()

    queue = getattr(request.app.state, "task_queue", None)
    if queue is not None:
        queue.enqueue(item_id)
    return {"status": "ok", "item_status": item.status}


@router.post("/items/{item_id}/resummarize")
def resummarize(item_id: str, request: Request, db: Any = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    if not item.batch_id:
        item.batch_id = str(uuid4())
    item.status = "summarizing"  # transcript 已存，跳过转写；向量先删后写
    item.error_msg = ""
    db.commit()

    queue = getattr(request.app.state, "task_queue", None)
    if queue is not None:
        queue.enqueue(item_id)
    return {"status": "ok", "item_status": item.status}


@router.post("/items/{item_id}/collection-summary")
async def collection_summary(item_id: str, db: Any = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")

    settings = load_settings(db)
    siblings = db.query(Item).filter(Item.video_id == item.video_id).all()
    combined = "\n\n".join(it.transcript for it in siblings if it.transcript)

    client = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    summary = await llm_summarize(combined, client, model=settings.llm_model)

    existing = (
        db.query(CollectionSummary).filter(CollectionSummary.video_id == item.video_id).first()
    )
    if existing is None:
        existing = CollectionSummary(
            video_id=item.video_id, summary_json=summary, model=settings.llm_model
        )
        db.add(existing)
    else:
        existing.summary_json = summary
        existing.model = settings.llm_model
    db.commit()
    return summary
