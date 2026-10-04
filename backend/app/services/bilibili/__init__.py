"""B 站服务封装（只读）：扫码登录、wbi 签名、字幕、DASH 音频、收藏夹。"""

from __future__ import annotations

from .client import BilibiliClient
from .wbi import extract_key_from_url, get_mixin_key, sign_params

__all__ = ["BilibiliClient", "extract_key_from_url", "get_mixin_key", "sign_params"]
