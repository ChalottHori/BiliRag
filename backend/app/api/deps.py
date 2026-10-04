"""FastAPI 依赖：DB session 与配置加载。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import Depends

from ..config import Settings, load_settings
from ..db import get_session_factory


def get_db() -> Iterator[Any]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def get_settings(db: Any = Depends(get_db)) -> Settings:
    return load_settings(db)
