"""BiliRag 应用入口（B-1 最小可启动空壳）。

仅提供 `/health`；建表 / FTS5 / 默认配置在 lifespan 中完成。
完整路由注册与 SSE / 静态托管由 B-4 负责。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db
from .logging_config import setup_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_db()
    yield


app = FastAPI(title="BiliRag", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
