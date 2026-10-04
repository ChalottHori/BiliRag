"""B 站 wbi 签名（纯逻辑，无网络依赖，可离线测试）。

算法：由 nav 接口返回的 `img_key`/`sub_key` 经固定置换表混合得到 32 位 `mixin_key`，
再对请求参数排序拼接后做 md5 得到 `w_rid`。
"""

from __future__ import annotations

import hashlib
import time
from urllib.parse import quote

# B 站公开的 wbi 混合置换表（64 位）。
_MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]

# 值中需要过滤的字符（B 站约定）。
_VALUE_FILTER = frozenset("!'()*")


def extract_key_from_url(url: str) -> str:
    """从 wbi img/sub 的 URL 提取文件名（不含扩展名）作为 key。"""
    return url.rsplit("/", 1)[-1].split(".")[0]


def get_mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in _MIXIN_KEY_ENC_TAB)[:32]


def _enc(value: str) -> str:
    return quote(value, safe="")


def _clean(value: object) -> str:
    return "".join(ch for ch in str(value) if ch not in _VALUE_FILTER)


def sign_params(
    params: dict[str, object], mixin_key: str, wts: int | None = None
) -> dict[str, object]:
    """为参数补充 `wts` 与 `w_rid`。`wts` 可注入以便测试确定性。"""
    ts = wts if wts is not None else int(time.time())
    signed: dict[str, object] = dict(params)
    signed["wts"] = ts

    query = "&".join(f"{_enc(k)}={_enc(_clean(v))}" for k, v in sorted(signed.items()))
    signed["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return signed
