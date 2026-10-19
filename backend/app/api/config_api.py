"""系统配置（§7.7）：读取（脱敏）与更新。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..config import load_settings
from ..models import Setting
from ..schemas import SettingsRead, SettingsUpdate
from ..security import encrypt
from .deps import get_db

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_config(db: Any = Depends(get_db)) -> SettingsRead:
    settings = load_settings(db)
    masked = "••••••" if settings.llm_api_key else ""
    return SettingsRead(
        llm_base_url=settings.llm_base_url,
        llm_api_key_masked=masked,
        llm_model=settings.llm_model,
        qa_llm_model=settings.qa_llm_model,
        asr_model=settings.asr_model,
        concurrency=settings.concurrency,
        data_dir=settings.data_dir,
        export_dir=settings.export_dir,
        keep_audio=settings.keep_audio,
        chunk_size=settings.chunk_size,
        top_k=settings.top_k,
        chat_use_llm_router=settings.chat_use_llm_router,
        chat_use_react=settings.chat_use_react,
        chat_use_verification=settings.chat_use_verification,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
    )


@router.put("/config")
def update_config(req: SettingsUpdate, db: Any = Depends(get_db)) -> dict[str, str]:
    row = db.get(Setting, "1")
    if row is None:
        row = Setting(id="1")
        db.add(row)

    data = req.model_dump(exclude_unset=True)
    if data.get("llm_api_key"):
        data["llm_api_key"] = encrypt(data["llm_api_key"])

    for field, value in data.items():
        if value is not None:
            setattr(row, field, value)
    db.commit()
    return {"status": "ok"}
