"""BiliRag 应用入口。

lifespan：建表 → 恢复非终态条目 → 启动 worker（线程池）。
- `GET /api/events`：SSE 进度推送（EventBus）。
- `POST /api/chat`：流式 `StreamingResponse`（fetch + ReadableStream 消费）。
- 前端 build（`frontend/dist`）存在时静态托管。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, backup, chat, config_api, export, folders, import_, items, summarize
from .config import load_settings
from .db import get_session_factory, init_db
from .logging_config import setup_logging
from .services.pipeline import build_handler
from .services.queue import EventBus, TaskQueue, recover_non_terminal

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()

    with get_session_factory()() as session:
        settings = load_settings(session)

    task_queue = TaskQueue(concurrency=settings.concurrency)
    bus = task_queue.event_bus
    task_queue.set_handler(build_handler(bus))
    bus.attach_loop(asyncio.get_running_loop())

    app.state.task_queue = task_queue
    app.state.event_bus = bus
    app.state.settings = settings

    # 断点续跑：恢复非终态条目
    with get_session_factory()() as session:
        recovered = recover_non_terminal(session)
    if recovered:
        task_queue.enqueue_many(recovered)

    yield

    task_queue.shutdown(wait=False)


app = FastAPI(title="BiliRag", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/events")
async def events(request: Request) -> StreamingResponse:
    bus: EventBus = request.app.state.event_bus

    async def gen() -> AsyncIterator[str]:
        queue = bus.subscribe()
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream")


app.include_router(auth.router)
app.include_router(folders.router)
app.include_router(import_.router)
app.include_router(summarize.router)
app.include_router(items.router)
app.include_router(chat.router)
app.include_router(export.router)
app.include_router(backup.router)
app.include_router(config_api.router)

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
