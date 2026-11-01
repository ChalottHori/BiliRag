"""数据目录备份（§7.7）：整目录复制到 backups/。"""

from __future__ import annotations

import shutil
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .deps import get_settings

router = APIRouter(prefix="/api", tags=["backup"])


@router.post("/backup")
def backup_now(settings: Any = Depends(get_settings)) -> dict[str, str]:
    """把整个数据目录复制到 `data_path.parent / "backups" / backup-<时间戳>`。

    同步端点，FastAPI 会在线程池执行，避免阻塞事件循环。
    """
    dest = settings.data_path.parent / "backups" / f"backup-{datetime.now():%Y%m%d-%H%M%S}"
    try:
        shutil.copytree(settings.data_path, dest)
    except Exception as exc:  # noqa: BLE001 - 备份失败需把原因返回给前端
        raise HTTPException(status_code=500, detail=f"备份失败：{exc}") from exc
    return {"status": "ok", "backup_dir": str(dest)}
