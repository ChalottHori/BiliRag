"""收藏夹响应模型。"""

from __future__ import annotations

from datetime import datetime

from .common import ORMModel


class FolderRead(ORMModel):
    id: str
    fid: str | None
    title: str
    kind: str
    media_count: int
    is_watch_later: bool
    synced_at: datetime | None
