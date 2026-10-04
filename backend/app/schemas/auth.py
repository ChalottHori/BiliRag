"""B 站登录态响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class BilibiliStatusRead(BaseModel):
    logged_in: bool
    user_name: str = ""
    user_mid: str = ""
    status: str = ""
