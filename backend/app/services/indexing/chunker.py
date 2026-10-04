"""全文稿切块（用于 embedding，按字符数切分）。"""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 0) -> list[str]:
    """按字符数切块，可带重叠。空文本返回空列表。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks
