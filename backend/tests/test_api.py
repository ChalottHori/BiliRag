"""API 集成测试（mock 全部外部依赖）。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_config_get_and_put(client: TestClient) -> None:
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["llm_api_key_masked"] == ""

    resp = client.put(
        "/api/config", json={"llm_api_key": "sk-123", "llm_model": "gpt", "asr_model": "small"}
    )
    assert resp.status_code == 200

    data = client.get("/api/config").json()
    assert data["llm_api_key_masked"] == "••••••"
    assert data["asr_model"] == "small"


def test_auth_status_logout(client: TestClient) -> None:
    assert client.get("/api/bilibili/status").json()["logged_in"] is False
    assert client.post("/api/bilibili/logout").json() == {"status": "ok"}


def test_qrcode_login_flow(client: TestClient) -> None:
    assert client.post("/api/bilibili/qrcode/generate").json()["qrcode_key"] == "K123"
    resp = client.get("/api/bilibili/qrcode/poll/K123")
    assert resp.json()["status"] == "success"

    status = client.get("/api/bilibili/status").json()
    assert status["logged_in"] is True
    assert status["user_name"] == "测试用户"


def test_folders_list_has_uncategorized(client: TestClient) -> None:
    kinds = [f["kind"] for f in client.get("/api/folders").json()]
    assert "uncategorized" in kinds


def test_folders_sync_and_videos(client: TestClient) -> None:
    assert client.post("/api/folders/sync").json()["count"] == 1
    folders = client.get("/api/folders").json()
    folder = next(f for f in folders if f["title"] == "默认收藏夹")
    assert client.get(f"/api/folders/{folder['id']}/videos").json()["total"] == 1


def test_folders_uncategorized_videos_empty(client: TestClient) -> None:
    folders = client.get("/api/folders").json()
    uncat = next(f for f in folders if f["kind"] == "uncategorized")
    resp = client.get(f"/api/folders/{uncat['id']}/videos")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_import_parse_confirm_and_summarize(client: TestClient) -> None:
    bvid = "BV1xx411c7mD"
    parsed = client.post(
        "/api/import/parse", json={"links": [f"https://www.bilibili.com/video/{bvid}"]}
    ).json()[0]
    assert parsed["bvid"] == bvid

    resp = client.post(
        "/api/import/confirm",
        json={"targets": [{"bvid": bvid, "cid": 1, "title": "测试视频", "part_title": "P1"}]},
    )
    assert resp.json()["created"] == 1
    item_id = resp.json()["item_ids"][0]

    client.app.state.task_queue.shutdown(wait=True)
    assert client.get(f"/api/items/{item_id}").json()["status"] == "done"


def test_items_list_move_delete(client: TestClient) -> None:
    resp = client.post(
        "/api/summarize",
        json={"targets": [{"bvid": "BV2", "cid": 2, "title": "视频2", "part_title": "P1"}]},
    )
    item_id = resp.json()["item_ids"][0]
    client.app.state.task_queue.shutdown(wait=True)

    assert client.get("/api/items").json()["total"] == 1
    assert client.post("/api/items/move", json={"ids": [item_id]}).json()["status"] == "ok"
    assert client.delete(f"/api/items/{item_id}").json()["status"] == "ok"
    assert client.get("/api/items").json()["total"] == 0


def test_chat_stream_and_history(client: TestClient) -> None:
    resp = client.post("/api/chat", json={"question": "测试问题"})
    assert resp.status_code == 200
    assert '"delta"' in resp.text
    assert '"done"' in resp.text
    # 无库内数据时路由到 direct，且仍推送 route / sources 事件
    assert '"type": "route"' in resp.text
    assert '"route": "direct"' in resp.text
    assert '"label": "直接回答"' in resp.text
    assert '"type": "sources"' in resp.text

    sessions = client.get("/api/chat/sessions").json()
    assert len(sessions) == 1
    sid = sessions[0]["id"]

    messages = client.get(f"/api/chat/sessions/{sid}/messages").json()
    assert len(messages) == 2  # user + assistant

    patched = client.patch(
        f"/api/chat/sessions/{sid}", json={"title": "新标题", "pinned": True}
    ).json()
    assert patched["title"] == "新标题"
    assert patched["pinned"] is True

    assert client.get("/api/chat/search", params={"q": "这是答案"}).json()["total"] >= 1

    exported = client.post(f"/api/chat/sessions/{sid}/export")
    assert exported.status_code == 200
    assert "新标题" in exported.text

    assert client.delete(f"/api/chat/sessions/{sid}").json()["status"] == "ok"


def test_chat_vector_route_and_keyword_citation(client: TestClient) -> None:
    # 入库一个标题命中的条目，让「量子」这类主题问题经 direct 纠偏进入 vector 检索。
    resp = client.post(
        "/api/summarize",
        json={"targets": [{"bvid": "BV9", "cid": 9, "title": "量子力学"}]},
    )
    item_id = resp.json()["item_ids"][0]
    client.app.state.task_queue.shutdown(wait=True)
    assert client.get(f"/api/items/{item_id}").json()["status"] == "done"

    resp = client.post("/api/chat", json={"question": "量子"})
    assert resp.status_code == 200
    text = resp.text
    # 路由 + 检索 + 来源事件
    assert '"route": "vector"' in text
    assert '"label": "检索知识库"' in text
    assert '"type": "retrieval"' in text
    assert '"keyword_count": 1' in text
    assert '"final_count": 1' in text
    assert '"type": "sources"' in text
    # citation 兼容 keyword 文档（带 item_id / bvid / title）
    assert '"done"' in text
    assert '"BV9"' in text
    assert '"量子力学"' in text
    assert f'"item_id": "{item_id}"' in text


def test_export_markdown(client: TestClient) -> None:
    client.post(
        "/api/summarize",
        json={"targets": [{"bvid": "BV3", "cid": 3, "title": "视频3", "part_title": "P1"}]},
    )
    client.app.state.task_queue.shutdown(wait=True)

    result = client.post("/api/export/markdown", json={"all": True}).json()
    assert result["count"] == 1
    assert result["files"]


def test_tasks_returns_snapshot_shape(client: TestClient) -> None:
    snapshot = client.get("/api/tasks").json()
    assert set(snapshot.keys()) == {"batch_id", "total", "done", "failed", "active", "items"}
    assert snapshot["total"] == 0
    assert snapshot["batch_id"] is None


def test_summarize_returns_batch_id(client: TestClient) -> None:
    resp = client.post(
        "/api/summarize",
        json={"targets": [{"bvid": "BV5", "cid": 5, "title": "t", "part_title": "p"}]},
    )
    assert resp.json()["batch_id"]
    assert resp.json()["created"] == 1


def test_tasks_snapshot_shows_failed_batch(client: TestClient) -> None:
    from app.db import get_session_factory
    from app.models import Item

    resp = client.post(
        "/api/summarize",
        json={"targets": [{"bvid": "BV6", "cid": 6, "title": "t", "part_title": "p"}]},
    )
    item_id = resp.json()["item_ids"][0]
    client.app.state.task_queue.shutdown(wait=True)

    with get_session_factory()() as session:
        item = session.get(Item, item_id)
        item.status = "failed"
        item.error_msg = "boom"
        session.commit()

    snapshot = client.get("/api/tasks").json()
    assert snapshot["failed"] == 1
    assert snapshot["total"] == 1
    assert snapshot["items"][0]["status"] == "failed"
    assert snapshot["items"][0]["error_msg"] == "boom"


def test_folder_videos_enriched_with_status(client: TestClient) -> None:
    client.post("/api/folders/sync")
    client.post(
        "/api/summarize",
        json={"targets": [{"bvid": "BV1", "cid": 1, "title": "视频1", "part_title": "P1"}]},
    )
    client.app.state.task_queue.shutdown(wait=True)

    folders = client.get("/api/folders").json()
    folder = next(f for f in folders if f["title"] == "默认收藏夹")
    videos = client.get(f"/api/folders/{folder['id']}/videos").json()["items"]
    assert videos[0]["parts_status"]["1"]["status"] == "done"
    assert videos[0]["parts_status"]["1"]["item_id"]


def test_chat_react_agent_steps(client, monkeypatch) -> None:
    from app.services.llm.client import LLMClient

    client.put("/api/config", json={"chat_use_react": True})
    resp = client.post(
        "/api/summarize", json={"targets": [{"bvid": "BV9", "cid": 9, "title": "量子力学"}]}
    )
    item_id = resp.json()["item_ids"][0]
    client.app.state.task_queue.shutdown(wait=True)
    assert client.get(f"/api/items/{item_id}").json()["status"] == "done"

    script = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"query": "量子"}'},
                }
            ],
        },
        {"role": "assistant", "content": "ReAct 答案"},
    ]

    async def fake_complete_message(
        self, messages, model=None, temperature=0.0, tools=None, tool_choice=None
    ):
        if tools is None:
            return {"role": "assistant", "content": "ReAct 答案"}
        return script.pop(0)

    monkeypatch.setattr(LLMClient, "complete_message", fake_complete_message)

    resp = client.post("/api/chat", json={"question": "量子"})
    text = resp.text
    assert '"type": "agent_step"' in text
    assert '"kind": "tool_call"' in text
    assert '"kind": "observation"' in text
    assert '"label": "多步检索"' in text
    assert '"type": "delta"' in text
    assert '"type": "done"' in text


def test_chat_react_falls_back_to_single_shot(client, monkeypatch) -> None:
    from app.services.llm.client import LLMClient

    client.put("/api/config", json={"chat_use_react": True})
    resp = client.post(
        "/api/summarize", json={"targets": [{"bvid": "BV9", "cid": 9, "title": "量子力学"}]}
    )
    item_id = resp.json()["item_ids"][0]
    client.app.state.task_queue.shutdown(wait=True)
    assert client.get(f"/api/items/{item_id}").json()["status"] == "done"

    async def fake_complete_message(
        self, messages, model=None, temperature=0.0, tools=None, tool_choice=None
    ):
        raise RuntimeError("tools unsupported")

    monkeypatch.setattr(LLMClient, "complete_message", fake_complete_message)

    resp = client.post("/api/chat", json={"question": "量子"})
    text = resp.text
    assert '"已回退单次检索"' in text
    assert '"type": "delta"' in text
    assert '"type": "done"' in text


def test_chat_verification_pass_frame_and_persist(client, monkeypatch) -> None:
    import app.api.chat as chat_mod

    async def fake_verify(question, answer, sources, evidence, verifier, model=None):
        return {"verdict": "pass", "issues": []}

    monkeypatch.setattr(chat_mod, "verify_answer", fake_verify)

    client.post(
        "/api/summarize", json={"targets": [{"bvid": "BV9", "cid": 9, "title": "量子力学"}]}
    )
    client.app.state.task_queue.shutdown(wait=True)

    resp = client.post("/api/chat", json={"question": "量子"})
    text = resp.text
    assert '"type": "verification"' in text
    assert '"verdict": "pass"' in text

    sid = client.get("/api/chat/sessions").json()[0]["id"]
    msgs = client.get(f"/api/chat/sessions/{sid}/messages").json()
    assert msgs[-1]["verdict_json"] == {"verdict": "pass", "issues": []}


def test_chat_verification_fail_persists(client, monkeypatch) -> None:
    import app.api.chat as chat_mod

    async def fake_verify(question, answer, sources, evidence, verifier, model=None):
        return {
            "verdict": "fail",
            "issues": [{"type": "unsupported_claim", "claim": "x", "reason": "无证据"}],
        }

    monkeypatch.setattr(chat_mod, "verify_answer", fake_verify)

    client.post(
        "/api/summarize", json={"targets": [{"bvid": "BV9", "cid": 9, "title": "量子力学"}]}
    )
    client.app.state.task_queue.shutdown(wait=True)

    resp = client.post("/api/chat", json={"question": "量子"})
    text = resp.text
    assert '"type": "verification"' in text
    assert '"verdict": "fail"' in text
    assert '"unsupported_claim"' in text

    sid = client.get("/api/chat/sessions").json()[0]["id"]
    msgs = client.get(f"/api/chat/sessions/{sid}/messages").json()
    assert msgs[-1]["verdict_json"]["verdict"] == "fail"
