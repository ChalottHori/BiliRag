"""切块单测。"""

from __future__ import annotations

from app.services.indexing.chunker import chunk_text


def test_empty() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text() -> None:
    assert chunk_text("短文本", chunk_size=100) == ["短文本"]


def test_chunking_no_overlap() -> None:
    assert chunk_text("abcdefghij", chunk_size=4, overlap=0) == ["abcd", "efgh", "ij"]


def test_chunking_with_overlap() -> None:
    assert chunk_text("abcdefghij", chunk_size=4, overlap=2) == [
        "abcd",
        "cdef",
        "efgh",
        "ghij",
        "ij",
    ]
