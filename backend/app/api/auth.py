"""扫码登录 / 会话（§7.1）。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends

from ..models import BilibiliSession
from ..security import encrypt
from ..services.bilibili import BilibiliClient
from .deps import get_db

router = APIRouter(prefix="/api/bilibili", tags=["auth"])

_POLL_STATUS = {86101: "waiting", 86090: "pending", 86038: "expired"}


@router.post("/qrcode/generate")
async def generate_qrcode() -> dict[str, str]:
    client = BilibiliClient()
    return await client.generate_qrcode()


@router.get("/qrcode/poll/{key}")
async def poll_qrcode(key: str, db: Any = Depends(get_db)) -> dict[str, Any]:
    client = BilibiliClient()
    result = await client.poll_qrcode(key)

    if result["code"] == 0:
        nav = await client.get_nav()
        session = BilibiliSession(
            cookies_encrypted=encrypt(json.dumps(client.cookies)),
            user_name=str(nav.get("uname", "")),
            user_mid=str(nav.get("mid", "")),
            status="active",
        )
        db.add(session)
        db.commit()
        return {
            "status": "success",
            "user_name": session.user_name,
            "user_mid": session.user_mid,
        }

    return {"status": _POLL_STATUS.get(result["code"], "failed"), "code": result["code"]}


@router.get("/status")
def status(db: Any = Depends(get_db)) -> dict[str, Any]:
    row = db.query(BilibiliSession).order_by(BilibiliSession.updated_at.desc()).first()
    if row is None:
        return {"logged_in": False}
    return {
        "logged_in": row.status == "active",
        "user_name": row.user_name,
        "user_mid": row.user_mid,
        "status": row.status,
    }


@router.post("/logout")
def logout(db: Any = Depends(get_db)) -> dict[str, str]:
    for row in db.query(BilibiliSession).all():
        row.status = "expired"
    db.commit()
    return {"status": "ok"}
