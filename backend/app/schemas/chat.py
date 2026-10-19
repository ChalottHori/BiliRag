"""问答会话 / 消息响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .common import ORMModel


class ChatSessionRead(ORMModel):
    id: str
    title: str
    pinned: bool
    created_at: datetime
    updated_at: datetime


class ChatMessageRead(ORMModel):
    id: str
    session_id: str
    role: str
    content: str
    citations_json: list[Any] | None
    verdict_json: dict[str, Any] | None
    created_at: datetime
