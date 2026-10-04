"""统一 httpx 客户端（单例）与指数退避重试装饰器。"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def retry_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    jitter: float = 0.2,
    exceptions: tuple[type[BaseException], ...] = (httpx.HTTPError,),
) -> Callable[[_F], _F]:
    """指数退避 + 抖动重试（异步）。用于 B 站 / LLM 网络请求。"""

    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt >= max_retries:
                        break
                    delay = base_delay * (backoff**attempt) * (1 + random.uniform(0, jitter))
                    logger.warning(
                        "网络请求失败（%s），%.2fs 后重试 %d/%d",
                        exc,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return cast(_F, wrapper)

    return decorator
