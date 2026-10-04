"""收藏夹 / 虚拟目录。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_id


class Folder(Base):
    __tablename__ = "folder"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fid: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 「未分类」为 null
    title: Mapped[str] = mapped_column(String(512), default="")
    kind: Mapped[str] = mapped_column(String(32), default="bilibili")
    media_count: Mapped[int] = mapped_column(Integer, default=0)
    is_watch_later: Mapped[bool] = mapped_column(Boolean, default=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
