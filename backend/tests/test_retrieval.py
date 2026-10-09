"""检索纯函数单测。"""

from __future__ import annotations

import types

from app.services.retrieval import (
    build_snippet,
    document_identity,
    extract_keywords,
    keyword_score,
    merge_ranked_documents,
)


def _doc(
    item_id: str, bvid: str, chunk_idx: int = 0, doc_type: str = "chunk"
) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        metadata={
            "item_id": item_id,
            "bvid": bvid,
            "doc_type": doc_type,
            "chunk_idx": chunk_idx,
        }
    )


# ---------- extract_keywords ----------


def test_extract_keywords_empty() -> None:
    assert extract_keywords("") == []
    assert extract_keywords("   ") == []


def test_extract_keywords_english_tokens() -> None:
    kws = extract_keywords("quantum mechanics a computing")
    assert "quantum" in kws
    assert "mechanics" in kws
    assert "a" not in kws  # 单字符英文 token 被丢弃（正则要求至少 2 字符）


def test_extract_keywords_chinese_ngrams() -> None:
    kws = extract_keywords("深度学习与神经网络")
    assert "深度学习" in kws
    assert "神经网络" in kws

    kws2 = extract_keywords("量子")
    assert kws2 == ["量子"]


def test_extract_keywords_stopwords_removed() -> None:
    kws = extract_keywords("怎么理解量子纠缠")
    assert "怎么" not in kws
    assert "量子纠缠" in kws

    # 纯停用词 -> 无关键词
    assert extract_keywords("总结") == []


# ---------- keyword_score ----------


def test_keyword_score_weighting_title_owner_content() -> None:
    kws = ["量子"]
    title_hit = keyword_score(kws, title="量子物理")
    owner_hit = keyword_score(kws, owner_name="量子博主")
    content_hit = keyword_score(kws, content="量子内容")
    assert title_hit > owner_hit > content_hit

    # 具体权重：标题 8 > UP主 5 > 正文 1（"量子" 长度 2，权重因子 2）
    assert title_hit == 8.0 * 2
    assert owner_hit == 5.0 * 2
    assert content_hit == 1.0 * 2


def test_keyword_score_empty_and_no_hit() -> None:
    assert keyword_score([]) == 0.0
    assert keyword_score(["量子"]) == 0.0


# ---------- build_snippet ----------


def test_build_snippet_short_text() -> None:
    assert build_snippet("短文本", ["量子"]) == "短文本"


def test_build_snippet_around_first_hit() -> None:
    text = "前" * 300 + "量子纠缠" + "后" * 300
    snippet = build_snippet(text, ["量子纠缠"], max_length=100)
    assert "量子纠缠" in snippet
    assert len(snippet) <= 100 + 6  # 两端各最多三个省略号


def test_build_snippet_no_hit() -> None:
    text = "字" * 800
    snippet = build_snippet(text, ["不存在"], max_length=100)
    assert snippet.endswith("...")
    assert len(snippet) <= 103


# ---------- document_identity ----------


def test_document_identity_item_key() -> None:
    assert document_identity(_doc("42", "BV1", chunk_idx=-2, doc_type="keyword")) == "42:keyword:-2"
    assert document_identity(_doc("7", "BV2", chunk_idx=0)) == "7:chunk:0"
    # doc_type 缺失时默认 chunk
    doc = types.SimpleNamespace(metadata={"item_id": "9", "chunk_idx": 3})
    assert document_identity(doc) == "9:chunk:3"


def test_document_identity_fallback_to_id() -> None:
    doc = types.SimpleNamespace(metadata={"bvid": "BV1"})  # 无 item_id
    assert document_identity(doc) == str(id(doc))


# ---------- merge_ranked_documents ----------


def test_merge_rrf_score_and_order() -> None:
    a = _doc("1", "BV1")
    b = _doc("2", "BV2")
    rankings = {"vector": [a], "keyword": [a, b]}
    merged = merge_ranked_documents(
        rankings, top_k=2, channel_weights={"vector": 1.0, "keyword": 1.0}
    )
    assert merged == [a, b]
    # a 在两个通道都是 rank1：1.0/61 + 1.0/61 > b 的 1.0/62
    assert a.metadata["retrieval_score"] > b.metadata["retrieval_score"]


def test_merge_per_video_limit() -> None:
    d1 = _doc("1", "BV1", chunk_idx=0)
    d2 = _doc("2", "BV1", chunk_idx=1)
    d3 = _doc("3", "BV1", chunk_idx=2)
    d4 = _doc("4", "BV2", chunk_idx=0)
    rankings = {"vector": [d1, d2, d3, d4]}
    merged = merge_ranked_documents(rankings, top_k=3, per_video_limit=2)
    assert [doc.metadata["item_id"] for doc in merged] == ["1", "2", "4"]


def test_merge_deferred_backfill() -> None:
    d1 = _doc("1", "BV1", chunk_idx=0)
    d2 = _doc("2", "BV1", chunk_idx=1)
    d3 = _doc("3", "BV1", chunk_idx=2)
    rankings = {"vector": [d1, d2, d3]}
    merged = merge_ranked_documents(rankings, top_k=3, per_video_limit=2)
    assert [doc.metadata["item_id"] for doc in merged] == ["1", "2", "3"]


def test_merge_writes_retrieval_score() -> None:
    d1 = _doc("1", "BV1")
    merged = merge_ranked_documents({"vector": [d1]}, top_k=1)
    assert merged[0].metadata["retrieval_score"] == round(1.0 / 61, 6)


def test_merge_top_k_zero() -> None:
    assert merge_ranked_documents({"vector": [_doc("1", "BV1")]}, top_k=0) == []
