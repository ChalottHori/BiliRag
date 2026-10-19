"""来源一致性校验（纯逻辑 + 可注入 LLM client，便于 fake 单测）。

校验目标：答案正文与本次检索到的来源双向对齐——
1. 正文来源真实性：不得引用检索结果之外的标题/BV（编造来源）。
2. 结论落地性：事实性结论不得超出检索证据。

统一由一次 LLM 判定，外加一个免费的 BV 正则兜底（确定性、零成本）。
任何 LLM 异常 → `unknown`（fail-open，由调用方决定放行）。
"""

from __future__ import annotations

import json
import re
from typing import Any

BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")

_VALID_VERDICTS = ("pass", "fail", "unknown")

_SYSTEM_PROMPT = (
    "你是「来源一致性」校验器。给定用户问题、助手答案、本次检索到的有效来源（标题+BV）"
    "与证据片段，判断答案是否与来源严格对齐。只输出一个 JSON 对象，不要任何额外文字或代码块：\n"
    '{"verdict": "pass"|"fail", "issues": ['
    '{"type": "fabricated_source", "source": "被引用的来源", "reason": "..."}, '
    '{"type": "unsupported_claim", "claim": "无支撑的结论", "reason": "..."}]}\n'
    "判定规则：\n"
    "- 答案中提到的任何视频标题或 BV 号不在「有效来源」里 → 记一条 fabricated_source。\n"
    "- 答案中的事实性结论若不能被「证据片段」支持 → 记一条 unsupported_claim。\n"
    "- 若答案只是复述/概括证据且没有编造来源 → verdict=pass，issues=[]。"
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def scan_fabricated_bvids(answer: str, valid_bvids: set[str]) -> list[str]:
    """扫描答案中的 BV 号，返回不在有效集合里的（编造）BV。"""
    found = BV_RE.findall(answer or "")
    return [bvid for bvid in found if bvid not in valid_bvids]


def build_verifier_messages(
    question: str, answer: str, sources: list[dict[str, Any]], evidence: str
) -> list[dict[str, str]]:
    source_lines = (
        "\n".join(f"- {s.get('title', '')}（{s.get('bvid', '')}）" for s in sources) or "（无）"
    )
    user = (
        f"用户问题：{question}\n\n"
        f"有效来源：\n{source_lines}\n\n"
        f"证据片段：\n{evidence or '（无）'}\n\n"
        f"助手答案：\n{answer}"
    )
    return [{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_verdict(text: str) -> dict[str, Any]:
    """宽容解析 LLM 返回的 JSON；失败返回 unknown。"""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    data: Any = None
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        pass
    if not isinstance(data, dict):
        match = _JSON_RE.search(cleaned)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = None

    if not isinstance(data, dict):
        return {"verdict": "unknown", "issues": []}

    verdict = data.get("verdict", "unknown")
    if verdict not in _VALID_VERDICTS:
        verdict = "unknown"
    issues = data.get("issues") or []
    if not isinstance(issues, list):
        issues = []
    return {"verdict": verdict, "issues": issues}


def _merge_fabricated(verdict: dict[str, Any], fake_bvids: list[str]) -> dict[str, Any]:
    """把 BV 兜底命中的假 BV 并入判定：强制 fail 并追加 fabricated_source。"""
    if not fake_bvids:
        return verdict
    issues = list(verdict.get("issues") or [])
    for bvid in fake_bvids:
        issues.append(
            {"type": "fabricated_source", "source": bvid, "reason": "BV 号不在检索结果中"}
        )
    return {"verdict": "fail", "issues": issues}


async def verify_answer(
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    evidence: str,
    client: Any,
    model: str | None = None,
) -> dict[str, Any]:
    """校验答案：LLM 判定 + BV 兜底合并。任何异常 → unknown（fail-open）。

    `client` 只需实现 `complete(messages, model=None, temperature=0.0) -> str`。
    """
    valid_bvids = {str(s.get("bvid", "")) for s in sources if s.get("bvid")}
    fake_bvids = scan_fabricated_bvids(answer, valid_bvids)

    verdict: dict[str, Any] = {"verdict": "unknown", "issues": []}
    try:
        messages = build_verifier_messages(question, answer, sources, evidence)
        text = await client.complete(messages, model=model, temperature=0.0)
        verdict = parse_verdict(text)
    except Exception:  # noqa: BLE001  校验失败 fail-open，不阻塞主链路
        verdict = {"verdict": "unknown", "issues": []}

    return _merge_fabricated(verdict, fake_bvids)


def build_correction_feedback(verdict: dict[str, Any]) -> str:
    """把校验问题拼成负面反馈，供纠错重生成使用。"""
    issues = verdict.get("issues") or []
    lines = ["（来源一致性校验未通过，请修正后重新回答。）"]
    for issue in issues:
        kind = issue.get("type", "")
        if kind == "fabricated_source":
            source = issue.get("source", "")
            reason = issue.get("reason", "")
            suffix = f"，{reason}" if reason else ""
            lines.append(f"- 编造来源：你引用了「{source}」{suffix}。")
        elif kind == "unsupported_claim":
            claim = issue.get("claim", "")
            reason = issue.get("reason", "")
            suffix = f"，{reason}" if reason else ""
            lines.append(f"- 无支撑结论：「{claim}」{suffix}。")
    lines.append(
        "请删除编造来源，只依据给定内容作答；无支撑的结论请删除或改为仅陈述证据支持的部分。"
    )
    return "\n".join(lines)
