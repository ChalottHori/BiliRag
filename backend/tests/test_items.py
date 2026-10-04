"""条目去重（`(bvid, cid)`）与唯一约束单测。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import Base, Item
from app.models.enums import ItemStatus
from app.services.items import create_items


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_item_status_values() -> None:
    assert {s.value for s in ItemStatus} == {
        "pending",
        "transcribing",
        "summarizing",
        "done",
        "failed",
    }


def test_create_items_dedup() -> None:
    factory = _session_factory()
    targets = [{"bvid": "BV1", "cid": 1, "title": "t", "part_title": "p"}]
    with factory() as s:
        first = create_items(s, targets)
        assert len(first) == 1
        second = create_items(s, targets)  # 重复导入跳过
        assert len(second) == 0
        assert s.query(Item).count() == 1


def test_item_unique_bvid_cid_constraint() -> None:
    factory = _session_factory()
    with factory() as s:
        s.add(Item(video_id="v1", part_id="p1", bvid="BV1", cid=1))
        s.add(Item(video_id="v2", part_id="p2", bvid="BV1", cid=1))
        with pytest.raises(IntegrityError):
            s.commit()
