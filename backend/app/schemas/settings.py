"""系统配置请求 / 响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    """配置更新（仅允许改动的字段）。"""

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    qa_llm_model: str | None = None
    asr_model: str | None = None
    concurrency: int | None = None
    export_dir: str | None = None
    keep_audio: bool | None = None
    chunk_size: int | None = None
    top_k: int | None = None
    chat_use_llm_router: bool | None = None
    chat_use_react: bool | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None


class SettingsRead(BaseModel):
    """配置读取（`llm_api_key` 脱敏）。"""

    llm_base_url: str = ""
    llm_api_key_masked: str = ""
    llm_model: str = ""
    qa_llm_model: str = ""
    asr_model: str = "medium"
    concurrency: int = 1
    data_dir: str = ""
    export_dir: str = ""
    keep_audio: bool = False
    chunk_size: int = 1000
    top_k: int = 5
    chat_use_llm_router: bool = False
    chat_use_react: bool = False
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
