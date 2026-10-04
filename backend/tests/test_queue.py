"""任务队列 / 事件总线 / 断点续跑 单测。"""

from __future__ import annotations

import asyncio
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Item
from app.services.queue.events import EventBus
from app.services.queue.queue import TaskQueue
from app.services.queue.recovery import recover_non_terminal


def test_event_bus_roundtrip() -> None:
    bus = EventBus()

    async def main() -> list[dict]:
        bus.attach_loop(asyncio.get_running_loop())
        q = bus.subscribe()
        bus.publish({"type": "a"})
        bus.publish({"type": "b"})
        return [await asyncio.wait_for(q.get(), 1) for _ in range(2)]

    events = asyncio.run(main())
    assert [e["type"] for e in events] == ["a", "b"]


def test_task_queue_runs_handler() -> None:
    seen: list[str] = []
    lock = threading.Lock()

    def handler(item_id: str) -> None:
        with lock:
            seen.append(item_id)

    tq = TaskQueue(concurrency=2, handler=handler)
    tq.enqueue_many(["a", "b", "c"])
    tq.shutdown(wait=True)
    assert sorted(seen) == ["a", "b", "c"]


def test_task_queue_publishes_events_and_progress() -> None:
    tq = TaskQueue(concurrency=1, handler=lambda i: None)

    async def main() -> list[dict]:
        tq.event_bus.attach_loop(asyncio.get_running_loop())
        q = tq.event_bus.subscribe()
        tq.enqueue("item1")
        return [await asyncio.wait_for(q.get(), 2) for _ in range(2)]

    events = asyncio.run(main())
    tq.shutdown(wait=True)
    assert [e["type"] for e in events] == ["task_start", "task_done"]
    assert events[0]["item_id"] == "item1"
    assert tq.progress()["done"] == 1


def test_recover_non_terminal() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as s:
        s.add_all(
            [
                Item(video_id="v1", part_id="p1", bvid="BV1", cid=1, status="pending"),
                Item(video_id="v2", part_id="p2", bvid="BV2", cid=2, status="transcribing"),
                Item(video_id="v3", part_id="p3", bvid="BV3", cid=3, status="summarizing"),
                Item(video_id="v4", part_id="p4", bvid="BV4", cid=4, status="failed"),
                Item(video_id="v5", part_id="p5", bvid="BV5", cid=5, status="done"),
            ]
        )
        s.commit()

    with session_factory() as s:
        ids = recover_non_terminal(s)

    assert len(ids) == 3
    with session_factory() as s:
        statuses = {r.bvid: r.status for r in s.query(Item).all()}
    assert statuses["BV1"] == "pending"
    assert statuses["BV2"] == "pending"
    assert statuses["BV3"] == "summarizing"
    assert statuses["BV4"] == "failed"
    assert statuses["BV5"] == "done"
