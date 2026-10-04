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
    titles = [f["title"] for f in client.get("/api/folders").json()]
    assert "默认收藏夹" in titles
    assert client.get("/api/folders/1/videos").json()["total"] == 1


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


def test_export_markdown(client: TestClient) -> None:
    client.post(
        "/api/summarize",
        json={"targets": [{"bvid": "BV3", "cid": 3, "title": "视频3", "part_title": "P1"}]},
    )
    client.app.state.task_queue.shutdown(wait=True)

    result = client.post("/api/export/markdown", json={"all": True}).json()
    assert result["count"] == 1
    assert result["files"]
