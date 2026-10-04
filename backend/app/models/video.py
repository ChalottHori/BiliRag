"""视频（bv/aid 维度）与分P（cid 维度）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_id


class Video(Base):
    __tablename__ = "video"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    bvid: Mapped[str] = mapped_column(String(32), default="")
    aid: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(Text, default="")
    up_name: Mapped[str] = mapped_column(String(255), default="")
    pubdate: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    is_collection: Mapped[bool] = mapped_column(Boolean, default=False)
    is_invalid: Mapped[bool] = mapped_column(Boolean, default=False)


class Part(Base):
    __tablename__ = "part"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("video.id", ondelete="CASCADE"), index=True
    )
    cid: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int] = mapped_column(Integer, default=1)
    part_title: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
