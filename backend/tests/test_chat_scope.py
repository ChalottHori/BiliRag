"""检索范围（folder_ids / bvids）过滤测试。

覆盖：
- `_build_where` 纯函数：仅收藏夹 / 仅视频 / 并集 `$or` / 范围+时间 `$and` / 空。
- 通过关键词通道（真实 SQLite）验证 bvid 范围收窄、收藏夹范围、以及并集。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.chat import _build_where

# ---------- _build_where（纯函数） ----------


def test_build_where_empty() -> None:
    assert _build_where(None) is None
    assert _build_where({}) is None


def test_build_where_folder_only() -> None:
    assert _build_where({"folder_ids": ["f1"]}) == {"folder_id": {"$in": ["f1"]}}


def test_build_where_bvid_only() -> None:
    assert _build_where({"bvids": ["BV1"]}) == {"bvid": {"$in": ["BV1"]}}


def test_build_where_folder_and_bvid_union() -> None:
    assert _build_where({"folder_ids": ["f1"], "bvids": ["BV1"]}) == {
        "$or": [{"folder_id": {"$in": ["f1"]}}, {"bvid": {"$in": ["BV1"]}}]
    }


def test_build_where_scope_and_time() -> None:
    where = _build_where(
        {
            "folder_ids": ["f1"],
            "time_from": "2024-01-01T00:00:00",
            "time_to": "2024-12-31T00:00:00",
        }
    )
    assert where is not None
    assert where["$and"][0] == {"folder_id": {"$in": ["f1"]}}
    assert "$gte" in where["$and"][1]["pubdate_ts"]
    assert "$lte" in where["$and"][1]["pubdate_ts"]


# ---------- 关键词通道范围（集成，真实 SQLite） ----------


def _summarize(client: TestClient, bvid: str, cid: int, title: str, folder_id: str | None) -> None:
    client.post(
        "/api/summarize",
        json={
            "targets": [{"bvid": bvid, "cid": cid, "title": title, "part_title": "P1"}],
            "folder_id": folder_id,
        },
    )


def test_chat_bvid_scope_narrows_keyword(client: TestClient) -> None:
    _summarize(client, "BVAAA", 1, "量子力学", None)
    _summarize(client, "BVBBB", 2, "量子物理", None)
    client.app.state.task_queue.shutdown(wait=True)

    # 全库：两条标题都命中「量子」
    assert '"keyword_count": 2' in client.post("/api/chat", json={"question": "量子"}).text

    # 仅 BVAAA：只命中一条
    text = client.post("/api/chat", json={"question": "量子", "filter": {"bvids": ["BVAAA"]}}).text
    assert '"keyword_count": 1' in text
    assert '"BVAAA"' in text


def test_chat_folder_and_bvid_union(client: TestClient) -> None:
    client.post("/api/folders/sync")
    folder = next(f for f in client.get("/api/folders").json() if f["title"] == "默认收藏夹")

    _summarize(client, "BVAAA", 1, "量子力学", folder["id"])
    _summarize(client, "BVBBB", 2, "量子物理", None)
    client.app.state.task_queue.shutdown(wait=True)

    # 收藏夹范围：只有 A
    text = client.post(
        "/api/chat", json={"question": "量子", "filter": {"folder_ids": [folder["id"]]}}
    ).text
    assert '"keyword_count": 1' in text

    # bvid 范围：只有 B
    text = client.post("/api/chat", json={"question": "量子", "filter": {"bvids": ["BVBBB"]}}).text
    assert '"keyword_count": 1' in text

    # 并集：A + B
    text = client.post(
        "/api/chat",
        json={"question": "量子", "filter": {"folder_ids": [folder["id"]], "bvids": ["BVBBB"]}},
    ).text
    assert '"keyword_count": 2' in text


def test_chat_db_list_with_bvid_scope(client: TestClient) -> None:
    _summarize(client, "BVAAA", 1, "量子力学", None)
    client.app.state.task_queue.shutdown(wait=True)

    text = client.post(
        "/api/chat", json={"question": "有哪些视频", "filter": {"bvids": ["BVAAA"]}}
    ).text
    assert '"route": "db_list"' in text
    # 纯 bvid 范围不再早退：db_list 能取到该视频（来源带 bvid）
    assert '"bvid": "BVAAA"' in text
