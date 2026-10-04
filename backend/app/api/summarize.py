"""总结任务（§7.4）：批量创建条目并入队、进度、重试、重新总结、合集总摘要。"""

from __future__ import annotations

from typing import Any

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
    created = create_items(db, targets, source_type=req.source_type)

    queue = getattr(request.app.state, "task_queue", None)
    item_ids = [item.id for item in created]
    if queue is not None:
        queue.enqueue_many(item_ids)
    return {"created": len(created), "item_ids": item_ids}


@router.get("/tasks")
def tasks(request: Request) -> dict[str, Any]:
    queue = getattr(request.app.state, "task_queue", None)
    if queue is None:
        return {"total": 0, "done": 0, "failed": 0, "active": []}
    return queue.progress()


@router.post("/items/{item_id}/retry")
def retry(item_id: str, request: Request, db: Any = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
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
