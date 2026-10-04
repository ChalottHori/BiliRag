"""进程内任务队列 + worker 线程池（ThreadPoolExecutor，并发数=settings.concurrency）。

`enqueue` 将 item_id 提交到线程池执行 handler（跑完整流水线），并发布进度事件。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .events import EventBus

logger = logging.getLogger(__name__)


class TaskQueue:
    def __init__(
        self,
        concurrency: int = 1,
        handler: Callable[[str], None] | None = None,
    ) -> None:
        self._handler = handler
        self._bus = EventBus()
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, concurrency), thread_name_prefix="task-worker"
        )
        self._lock = threading.Lock()
        self._active: set[str] = set()
        self._total = 0
        self._done = 0
        self._failed = 0

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    def set_handler(self, handler: Callable[[str], None]) -> None:
        self._handler = handler

    def enqueue(self, item_id: str) -> None:
        with self._lock:
            self._active.add(item_id)
            self._total += 1
        self._executor.submit(self._run, item_id)

    def enqueue_many(self, item_ids: list[str]) -> None:
        for item_id in item_ids:
            self.enqueue(item_id)

    def _run(self, item_id: str) -> None:
        try:
            self._bus.publish({"type": "task_start", "item_id": item_id})
            if self._handler is not None:
                self._handler(item_id)
            with self._lock:
                self._done += 1
            self._bus.publish({"type": "task_done", "item_id": item_id})
        except Exception as exc:  # noqa: BLE001  失败不中断 worker
            logger.exception("任务处理失败 item_id=%s", item_id)
            with self._lock:
                self._failed += 1
            self._bus.publish({"type": "task_error", "item_id": item_id, "error": str(exc)})
        finally:
            with self._lock:
                self._active.discard(item_id)

    def progress(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total": self._total,
                "done": self._done,
                "failed": self._failed,
                "active": sorted(self._active),
            }

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)
