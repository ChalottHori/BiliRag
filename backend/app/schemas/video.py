"""视频 / 分P 响应模型。"""

from __future__ import annotations

from datetime import datetime

from .common import ORMModel


class VideoRead(ORMModel):
    id: str
    bvid: str
    aid: int
    title: str
    cover_url: str
    up_name: str
    pubdate: datetime | None
    duration: int
    is_collection: bool
    is_invalid: bool


class PartRead(ORMModel):
    id: str
    video_id: str
    cid: int
    page: int
    part_title: str
    duration: int
