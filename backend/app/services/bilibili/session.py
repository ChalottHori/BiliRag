"""B 站登录态 cookie 加载（解密）。"""

from __future__ import annotations

import json
from typing import Any

from ...models import BilibiliSession
from ...security import decrypt


def load_cookies(session: Any) -> dict[str, str]:
    """从最新一条 bilibili_session 中解密 cookie。"""
    row = session.query(BilibiliSession).order_by(BilibiliSession.updated_at.desc()).first()
    if row is not None and row.cookies_encrypted:
        try:
            return json.loads(decrypt(row.cookies_encrypted))
        except Exception:
            return {}
    return {}
