"""B 站登录态。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_id


class BilibiliSession(Base):
    __tablename__ = "bilibili_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cookies_encrypted: Mapped[str] = mapped_column(Text, default="")  # Fernet 加密 cookie JSON
    user_name: Mapped[str] = mapped_column(String(255), default="")
    user_mid: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
