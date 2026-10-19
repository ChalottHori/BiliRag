"""配置加载。

优先级：环境变量（`BILIRAG_*`）> SQLite `settings` 表 > 代码默认值。
数据目录（`data_dir`）是「自包含」运行目录，SQLite / Chroma / 缩略图 / 导出 / 日志 /
Fernet 密钥均位于其下。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BACKEND_DIR / "data"

ENV_PREFIX = "BILIRAG_"


class Settings(BaseModel):
    """运行期配置（与 `settings` 表一一对应）。"""

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    qa_llm_model: str = ""
    asr_model: str = "medium"
    concurrency: int = 1
    data_dir: str = str(DEFAULT_DATA_DIR)
    export_dir: str = str(DEFAULT_DATA_DIR / "exports")
    keep_audio: bool = False
    chunk_size: int = 1000
    top_k: int = 8
    chat_use_llm_router: bool = False
    chat_use_react: bool = False
    chat_use_verification: bool = True
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # ---- 派生路径 ----
    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def db_path(self) -> Path:
        return self.data_path / "app.db"

    @property
    def chroma_path(self) -> Path:
        return self.data_path / "chroma"

    @property
    def thumbnails_path(self) -> Path:
        return self.data_path / "thumbnails"

    @property
    def exports_path(self) -> Path:
        return Path(self.export_dir) if self.export_dir else self.data_path / "exports"

    @property
    def logs_path(self) -> Path:
        return self.data_path / "logs"

    @property
    def secret_key_path(self) -> Path:
        return self.data_path / ".secret_key"


# 字段名 -> 环境变量后缀（去掉前缀 `BILIRAG_`）
_ENV_MAP: dict[str, str] = {
    "llm_base_url": "LLM_BASE_URL",
    "llm_api_key": "LLM_API_KEY",
    "llm_model": "LLM_MODEL",
    "qa_llm_model": "QA_LLM_MODEL",
    "asr_model": "ASR_MODEL",
    "concurrency": "CONCURRENCY",
    "data_dir": "DATA_DIR",
    "export_dir": "EXPORT_DIR",
    "keep_audio": "KEEP_AUDIO",
    "chunk_size": "CHUNK_SIZE",
    "top_k": "TOP_K",
    "chat_use_llm_router": "CHAT_USE_LLM_ROUTER",
    "chat_use_react": "CHAT_USE_REACT",
    "chat_use_verification": "CHAT_USE_VERIFICATION",
    "embedding_provider": "EMBEDDING_PROVIDER",
    "embedding_model": "EMBEDDING_MODEL",
}


def _coerce(field: str, raw: str) -> Any:
    """按 `Settings` 字段类型把环境变量字符串转成对应类型。"""
    annotation = Settings.model_fields[field].annotation
    if annotation is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if annotation is int:
        return int(raw)
    return raw


def env_overrides() -> dict[str, Any]:
    """读取所有 `BILIRAG_*` 环境变量覆盖。"""
    out: dict[str, Any] = {}
    for field, suffix in _ENV_MAP.items():
        raw = os.environ.get(ENV_PREFIX + suffix)
        if raw is None:
            continue
        out[field] = _coerce(field, raw)
    return out


def get_data_dir() -> Path:
    """启动期数据目录（仅环境变量可覆盖，用于引导 DB 路径）。"""
    raw = os.environ.get(ENV_PREFIX + "DATA_DIR")
    return Path(raw) if raw else DEFAULT_DATA_DIR


def defaults() -> Settings:
    """返回纯默认配置（不含环境变量 / DB 覆盖）。"""
    return Settings()


def load_settings(session: Any | None = None) -> Settings:
    """合并 默认值 + 环境变量 + DB `settings` 表（环境变量优先级最高）。

    传入 SQLAlchemy `Session` 时读取 DB 配置；否则仅返回默认 + 环境变量。
    `llm_api_key` 在库中为加密存储，读取时解密为明文。
    """
    data: dict[str, Any] = env_overrides()

    if session is not None:
        from .models import Setting  # 延迟导入，避免循环

        row = session.get(Setting, "1")
        if row is not None:
            for field in Settings.model_fields:
                if field in data:
                    continue  # 环境变量优先
                value = getattr(row, field)
                if field == "llm_api_key" and value:
                    from .security import decrypt  # 延迟导入

                    value = decrypt(value)
                data[field] = value

    return Settings(**data)
