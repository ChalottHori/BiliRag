"""模型包：导入本包即把所有模型注册到 `Base.metadata`。"""

from __future__ import annotations

from .auth import BilibiliSession
from .base import Base, new_id
from .chat import ChatMessage, ChatSession
from .enums import FolderKind, ItemStatus, MessageRole, SessionStatus, SourceType
from .folder import Folder
from .item import CollectionSummary, Item
from .settings import Setting
from .video import Part, Video

__all__ = [
    "Base",
    "new_id",
    "BilibiliSession",
    "ChatMessage",
    "ChatSession",
    "CollectionSummary",
    "Folder",
    "Item",
    "Part",
    "Setting",
    "Video",
    "FolderKind",
    "ItemStatus",
    "MessageRole",
    "SessionStatus",
    "SourceType",
]
