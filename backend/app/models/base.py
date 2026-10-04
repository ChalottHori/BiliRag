"""ORM 基类与通用工具。"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有模型的声明式基类。"""


def new_id() -> str:
    """生成 UUID 主键字符串。"""
    return str(uuid4())
