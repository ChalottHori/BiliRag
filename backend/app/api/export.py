"""Markdown 导出（§7.7）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..services.export import export_items_markdown
from .deps import get_db, get_settings

router = APIRouter(prefix="/api", tags=["export"])


class ExportRequest(BaseModel):
    item_ids: list[str] | None = None
    folder_ids: list[str] | None = None
    all: bool = False
    dest_dir: str | None = None


@router.post("/export/markdown")
def export_markdown(
    req: ExportRequest, db: Any = Depends(get_db), settings: Any = Depends(get_settings)
) -> dict[str, Any]:
    return export_items_markdown(
        db,
        settings,
        item_ids=req.item_ids,
        folder_ids=req.folder_ids,
        export_all=req.all,
        dest_dir=req.dest_dir,
    )
