"""入库条目响应模型。"""

from __future__ import annotations

from datetime import datetime

from .common import ORMModel


class ItemRead(ORMModel):
    id: str
    bvid: str
    aid: int
    cid: int
    title: str
    part_title: str
    cover_url: str
    up_name: str
    pubdate: datetime | None
    duration: int
    source_type: str
    folder_id: str | None
    status: str
    error_msg: str
    chunk_count: int
    imported_at: datetime
    updated_at: datetime
