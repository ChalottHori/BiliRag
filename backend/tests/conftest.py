"""集成测试夹具：临时数据目录 + mock 全部外部依赖（B 站 / LLM / ASR / embedding / Chroma）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.db as db_module
from app.main import app
from app.services.bilibili.client import BilibiliClient
from app.services.indexing.embedder import Embedder
from app.services.indexing.store import VectorStore
from app.services.llm.client import LLMClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BILIRAG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(db_module, "_engine", None)
    monkeypatch.setattr(db_module, "_SessionLocal", None)

    # ---- 流水线外部步骤 mock ----
    async def fake_transcript(item, settings):
        return "这是一段测试全文稿"

    async def fake_summary(transcript, settings):
        return {
            "title": "测试标题",
            "overview": "概述",
            "points": ["要点1"],
            "keywords": ["关键词"],
        }

    def fake_index(item, transcript, settings):
        item.chunk_count = 1

    monkeypatch.setattr("app.services.pipeline._get_transcript", fake_transcript)
    monkeypatch.setattr("app.services.pipeline._summarize_transcript", fake_summary)
    monkeypatch.setattr("app.services.pipeline._index", fake_index)

    # ---- B 站客户端 mock ----
    async def fake_generate(self):
        return {"qrcode_url": "http://x/qr", "qrcode_key": "K123"}

    async def fake_poll(self, key):
        return {"code": 0, "data": {"url": "http://x/login"}, "cookies": {"SESSDATA": "s"}}

    async def fake_nav(self):
        return {"uname": "测试用户", "mid": "123", "isLogin": True}

    async def fake_get_folders(self, mid):
        return [{"fid": "1", "title": "默认收藏夹", "media_count": 1, "is_watch_later": False}]

    async def fake_get_folder_videos(self, fid, page=1, page_size=20):
        return {
            "videos": [
                {
                    "bvid": "BV1",
                    "aid": 1,
                    "title": "视频1",
                    "cover_url": "",
                    "up_name": "UP",
                    "pubdate": 0,
                    "duration": 60,
                    "is_collection": False,
                    "is_invalid": False,
                }
            ],
            "total": 1,
        }

    async def fake_get_video_info(self, bvid):
        return {
            "bvid": bvid,
            "aid": 1,
            "title": "测试视频",
            "cover_url": "http://x/c",
            "up_name": "UP主",
            "pubdate": 1700000000,
            "duration": 120,
            "is_collection": False,
            "is_invalid": False,
            "parts": [{"cid": 1, "page": 1, "part_title": "P1", "duration": 120}],
        }

    async def fake_get_video_parts(self, bvid):
        return [{"cid": 1, "page": 1, "part_title": "P1", "duration": 120}]

    monkeypatch.setattr(BilibiliClient, "generate_qrcode", fake_generate)
    monkeypatch.setattr(BilibiliClient, "poll_qrcode", fake_poll)
    monkeypatch.setattr(BilibiliClient, "get_nav", fake_nav)
    monkeypatch.setattr(BilibiliClient, "get_folders", fake_get_folders)
    monkeypatch.setattr(BilibiliClient, "get_folder_videos", fake_get_folder_videos)
    monkeypatch.setattr(BilibiliClient, "get_video_info", fake_get_video_info)
    monkeypatch.setattr(BilibiliClient, "get_video_parts", fake_get_video_parts)

    # ---- embedding / Chroma mock ----
    monkeypatch.setattr(Embedder, "embed", lambda self, texts: [[0.1, 0.2, 0.3] for _ in texts])
    monkeypatch.setattr(VectorStore, "add", lambda self, *a, **k: None)
    monkeypatch.setattr(VectorStore, "delete", lambda self, *a, **k: None)
    monkeypatch.setattr(VectorStore, "query", lambda self, *a, **k: [])

    # ---- LLM mock ----
    async def fake_stream(self, messages, model=None, temperature=0.0):
        yield "这是答案"

    async def fake_complete(self, messages, model=None, temperature=0.0, max_tokens=None):
        return '{"title": "t", "overview": "o", "points": [], "keywords": []}'

    monkeypatch.setattr(LLMClient, "stream_complete", fake_stream)
    monkeypatch.setattr(LLMClient, "complete", fake_complete)

    with TestClient(app) as c:
        yield c
