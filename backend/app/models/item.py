"""入库条目（分P粒度）与合集总摘要。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_id


class Item(Base):
    __tablename__ = "item"
    __table_args__ = (UniqueConstraint("bvid", "cid", name="uq_item_bvid_cid"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("video.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("part.id", ondelete="CASCADE"), index=True
    )

    # 冗余键，用于去重
    bvid: Mapped[str] = mapped_column(String(32), default="")
    aid: Mapped[int] = mapped_column(Integer, default=0)
    cid: Mapped[int] = mapped_column(Integer, default=0)

    # 元数据快照
    title: Mapped[str] = mapped_column(Text, default="")
    part_title: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(Text, default="")
    up_name: Mapped[str] = mapped_column(String(255), default="")
    pubdate: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=0)

    source_type: Mapped[str] = mapped_column(String(16), default="folder")
    folder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("folder.id", ondelete="SET NULL"), nullable=True, index=True
    )

    transcript: Mapped[str] = mapped_column(Text, default="")
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class CollectionSummary(Base):
    __tablename__ = "collection_summary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("video.id", ondelete="CASCADE"), index=True
    )
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
