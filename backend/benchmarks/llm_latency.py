"""实测：LLM 流式首 token 延迟（TTFT）。

调用 settings 表里已配置的 LLM（OpenAI 兼容 /stream），每条问题只取到
首个 chunk 即断开，因此成本极小（仅首 token 计费）。
样本 3 条，覆盖三类路由入口（寒暄 / 清单 / 总结），冷热连接各取一次。
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from app.config import load_settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.services.llm import LLMClient  # noqa: E402

QUESTIONS = [
    "你好，请介绍一下你自己",  # direct 路由：不检索，纯生成
    "我的知识库里收藏了哪些视频？",  # db_list 路由
    "帮我总结一下这些视频都讲了什么",  # db_content 路由
]


async def ttft_ms(client: LLMClient, question: str) -> float:
    """返回首个 content chunk 的到达耗时（毫秒）。"""
    t0 = time.perf_counter()
    async for _ in client.stream_complete([{"role": "user", "content": question}], temperature=0.0):
        return (time.perf_counter() - t0) * 1000
    return (time.perf_counter() - t0) * 1000  # 无 chunk 时兜底


async def main() -> None:
    with get_session_factory()() as session:
        settings = load_settings(session)

    if not (settings.llm_base_url and settings.llm_model):
        print("LLM 未配置，跳过。")
        return

    client = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    print(f"LLM 端点: {settings.llm_base_url}")
    print(f"模型    : {settings.llm_model}")
    print("-" * 60)

    samples = []
    for i, q in enumerate(QUESTIONS, 1):
        ms = await ttft_ms(client, q)
        samples.append(ms)
        tag = "（冷连接，含建连）" if i == 1 else ""
        print(f"  {i}. TTFT {ms:7.0f} ms {tag}  <- {q}")

    warm = samples[1:]  # 去掉首条冷连接
    print("-" * 60)
    print(f"首 token 延迟：首条(冷) {samples[0]:.0f} ms / 后续(热) 平均 {sum(warm) / len(warm):.0f} ms")


if __name__ == "__main__":
    asyncio.run(main())
