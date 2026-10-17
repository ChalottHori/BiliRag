"""系统配置（单行）。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="1")
    llm_base_url: Mapped[str] = mapped_column(Text, default="")
    llm_api_key: Mapped[str] = mapped_column(Text, default="")  # Fernet 加密存储
    llm_model: Mapped[str] = mapped_column(Text, default="")
    qa_llm_model: Mapped[str] = mapped_column(Text, default="")
    asr_model: Mapped[str] = mapped_column(String(32), default="medium")
    concurrency: Mapped[int] = mapped_column(Integer, default=1)
    data_dir: Mapped[str] = mapped_column(Text, default="")
    export_dir: Mapped[str] = mapped_column(Text, default="")
    keep_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    chunk_size: Mapped[int] = mapped_column(Integer, default=1000)
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    chat_use_llm_router: Mapped[bool] = mapped_column(Boolean, default=False)
    chat_use_react: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_provider: Mapped[str] = mapped_column(String(16), default="local")
    embedding_model: Mapped[str] = mapped_column(Text, default="BAAI/bge-small-zh-v1.5")
