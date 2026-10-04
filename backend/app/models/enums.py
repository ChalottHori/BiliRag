"""领域枚举（对应 requirements.md §6.2 与各字段说明）。"""

from __future__ import annotations

from enum import StrEnum


class ItemStatus(StrEnum):
    """入库条目状态机（§6.2）。"""

    pending = "pending"
    transcribing = "transcribing"
    summarizing = "summarizing"
    done = "done"
    failed = "failed"


class SourceType(StrEnum):
    folder = "folder"
    link = "link"


class FolderKind(StrEnum):
    bilibili = "bilibili"
    uncategorized = "uncategorized"


class SessionStatus(StrEnum):
    active = "active"
    expired = "expired"


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
