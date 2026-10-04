"""断点续跑（决策 3）：应用启动时扫描非终态条目并重新入队。"""

from __future__ import annotations

from typing import Any

from ...models import Item

_NON_TERMINAL = ("pending", "transcribing", "summarizing")


def recover_non_terminal(session: Any) -> list[str]:
    """扫描非终态条目，重置状态并返回需重新入队的 item_id 列表。

    - `pending` / `transcribing` → 重置为 `pending`（从头跑）。
    - `summarizing` → 保留（`transcript` 已存，跳过转写）。
    - `failed` / `done` → 不动。
    """
    rows = session.query(Item).filter(Item.status.in_(_NON_TERMINAL)).all()
    ids: list[str] = []
    for row in rows:
        if row.status in ("pending", "transcribing"):
            row.status = "pending"
        ids.append(row.id)
    session.commit()
    return ids
