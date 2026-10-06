"""单个 item 的总结流水线（转写 → 摘要 → 向量化），在 worker 线程中执行。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from ..config import Settings, load_settings
from ..db import get_session_factory
from ..models import Item
from .asr import WhisperTranscriber
from .bilibili import BilibiliClient
from .bilibili.session import load_cookies
from .indexing import Embedder, VectorStore, chunk_text
from .llm import LLMClient, summarize
from .queue import EventBus

logger = logging.getLogger(__name__)


def _load_cookies() -> dict[str, str]:
    with get_session_factory()() as session:
        return load_cookies(session)


async def _get_transcript(item: Item, settings: Settings) -> str:
    # 流水线在 worker 线程内用 asyncio.run 跑，每次都是全新的事件循环；
    # 必须新建客户端，不能复用绑定到其它循环的全局单例（否则报 "different event loop"）。
    cookies = _load_cookies()
    logger.info("流水线加载登录 cookie：keys=%s", list(cookies.keys()))
    if "SESSDATA" not in cookies:
        logger.warning("未检测到 SESSDATA cookie，登录态可能未保存，请重新扫码登录")
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True) as http:
        client = BilibiliClient(client=http, cookies=cookies)
        text = await client.get_subtitle_text(item.bvid, item.cid)
        if text:
            return text

        audio_dir = settings.data_path / "audio"
        audio_path = await client.download_audio(item.bvid, item.cid, audio_dir)

    transcriber = WhisperTranscriber(model_size=settings.asr_model)
    result = transcriber.transcribe(audio_path)  # 阻塞，已在 worker 线程内
    if not settings.keep_audio:
        Path(audio_path).unlink(missing_ok=True)
    return result


async def _summarize_transcript(transcript: str, settings: Settings) -> dict[str, Any]:
    client = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    return await summarize(transcript, client, model=settings.llm_model)


def _index(item: Item, transcript: str, settings: Settings) -> None:
    chunks = chunk_text(transcript, settings.chunk_size)
    store = VectorStore(
        path=settings.chroma_path,
        embedder=Embedder(
            model_name=settings.embedding_model,
            provider=settings.embedding_provider,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        ),
    )
    store.delete(item.id)  # 先删后写，保证幂等（重新总结 / 重跑）
    store.add(
        item.id,
        chunks,
        {
            "video_id": item.video_id,
            "part_id": item.part_id,
            "folder_id": item.folder_id or "",
            "bvid": item.bvid,
            "cid": item.cid,
            "pubdate_ts": int(item.pubdate.timestamp()) if item.pubdate else 0,
        },
    )
    item.chunk_count = len(chunks)


def _emit(bus: EventBus | None, item_id: str, status: str, error: str = "") -> None:
    if bus is None:
        return
    event: dict[str, Any] = {"type": "item_status", "item_id": item_id, "status": status}
    if error:
        event["error"] = error
    bus.publish(event)


def process_item(item_id: str, bus: EventBus | None = None) -> None:
    factory = get_session_factory()
    with factory() as session:
        item = session.get(Item, item_id)
        if item is None:
            return
        settings = load_settings(session)
        try:
            _run_pipeline(session, item, settings, bus)
        except Exception as exc:  # noqa: BLE001  业务失败标记 failed，不中断 worker
            item.status = "failed"
            item.error_msg = str(exc)
            session.commit()
            _emit(bus, item_id, "failed", str(exc))
            logger.exception("流水线失败 item_id=%s", item_id)


def _run_pipeline(session: Any, item: Item, settings: Settings, bus: EventBus | None) -> None:
    # 1. 转写（summarizing 说明 transcript 已存，跳过转写）
    if item.status != "summarizing":
        item.status = "transcribing"
        session.commit()
        _emit(bus, item.id, "transcribing")

        item.transcript = asyncio.run(_get_transcript(item, settings))
        item.status = "summarizing"
        session.commit()
        _emit(bus, item.id, "summarizing")

    # 2. 摘要
    item.summary_json = asyncio.run(_summarize_transcript(item.transcript, settings))
    session.commit()

    # 3. 向量化
    _index(item, item.transcript, settings)
    item.status = "done"
    session.commit()
    _emit(bus, item.id, "done")


def build_handler(bus: EventBus | None = None) -> Callable[[str], None]:
    def handler(item_id: str) -> None:
        process_item(item_id, bus)

    return handler
