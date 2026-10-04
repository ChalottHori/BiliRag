"""Fernet 加解密：cookie 与 LLM api_key 的落盘加密。

密钥独立存于 `data/.secret_key`（与 `app.db` 分离），首次运行自动生成。
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

from .config import get_data_dir


def _key_path() -> Path:
    return get_data_dir() / ".secret_key"


def _load_key() -> bytes:
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes()
    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows 下 chmod 语义有限，忽略
    return key


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_key())
    return _fernet


def encrypt(plaintext: str) -> str:
    """加密明文，返回 Fernet token 字符串；空串原样返回。"""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """解密 Fernet token，返回明文；空串原样返回。"""
    if not token:
        return ""
    return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
