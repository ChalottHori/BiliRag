"""通用 Schema 基类。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """允许从 SQLAlchemy ORM 对象直接构造的响应模型基类。"""

    model_config = ConfigDict(from_attributes=True)
