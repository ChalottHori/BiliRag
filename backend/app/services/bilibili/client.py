"""B 站客户端（只读）。

统一走 `httpx.AsyncClient`；请求携带 cookie、UA、Referer，并对 412/429 限流做退避重试。
`_get_json` 解析 B 站标准响应体 `{code, message, data}`，业务错误抛异常。
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from ..http import USER_AGENT, get_client
from .wbi import extract_key_from_url, get_mixin_key, sign_params

logger = logging.getLogger(__name__)


class BilibiliError(Exception):
    """B 站业务错误（code != 0）。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"bilibili error {code}: {message}")
        self.code = code
        self.message = message


class BilibiliClient:
    API = "https://api.bilibili.com"
    PASSPORT = "https://passport.bilibili.com"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self._client = client
        self._cookies = dict(cookies or {})
        self._mixin_key: str | None = None
        self._mixin_key_ts: float = 0.0

    # ------------------------------------------------------------------ 基础
    def _http(self) -> httpx.AsyncClient:
        return self._client or get_client()

    @property
    def cookies(self) -> dict[str, str]:
        return self._cookies

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        max_retries: int = 3,
    ) -> httpx.Response:
        http = self._http()
        merged_headers = {"User-Agent": USER_AGENT, "Referer": "https://www.bilibili.com"}
        merged_headers.update(headers or {})
        merged_cookies = {**self._cookies, **(cookies or {})}

        last: httpx.Response | None = None
        for attempt in range(max_retries + 1):
            resp = await http.request(
                method,
                url,
                params=params,
                json=json,
                headers=merged_headers,
                cookies=merged_cookies or None,
            )
            if resp.status_code in (412, 429):
                last = resp
                await asyncio.sleep(1.0 * (2**attempt))
                continue
            resp.raise_for_status()
            return resp
        assert last is not None
        last.raise_for_status()
        return last

    async def _get_json(self, url: str, *, params: dict[str, Any] | None = None, **kw: Any) -> Any:
        resp = await self._request("GET", url, params=params, **kw)
        payload = resp.json()
        code = payload.get("code", -1)
        if code != 0:
            raise BilibiliError(code, payload.get("message", "unknown error"))
        return payload.get("data")

    async def _get_wbi(self, force: bool = False) -> str:
        """获取并缓存 wbi mixin_key（约 1 小时有效）。"""
        now = time.time()
        if self._mixin_key is not None and (now - self._mixin_key_ts) < 3600 and not force:
            return self._mixin_key
        nav = await self._get_json(f"{self.API}/x/web-interface/nav")
        wbi_img = nav.get("wbi_img", {})
        img_key = extract_key_from_url(wbi_img.get("img_url", ""))
        sub_key = extract_key_from_url(wbi_img.get("sub_url", ""))
        self._mixin_key = get_mixin_key(img_key, sub_key)
        self._mixin_key_ts = now
        return self._mixin_key

    # ------------------------------------------------------------------ 登录
    async def generate_qrcode(self) -> dict[str, str]:
        data = await self._get_json(
            f"{self.PASSPORT}/x/passport-login/web/qrcode/generate",
        )
        return {"qrcode_url": data["url"], "qrcode_key": data["qrcode_key"]}

    async def poll_qrcode(self, qrcode_key: str) -> dict[str, Any]:
        """轮询扫码状态。非 0 code 是正常中间态，不作为业务错误抛出。"""
        resp = await self._request(
            "GET",
            f"{self.PASSPORT}/x/passport-login/web/qrcode/poll",
            params={"qrcode_key": qrcode_key},
        )
        payload = resp.json()
        result: dict[str, Any] = {
            "code": payload.get("code", -1),
            "message": payload.get("message", ""),
            "data": payload.get("data") or {},
        }
        # code==0 表示扫码成功，返回的 url 需访问以换取 cookie
        if result["code"] == 0 and result["data"].get("url"):
            resp2 = await self._request("GET", result["data"]["url"])
            self._cookies = dict(resp2.cookies)
            result["cookies"] = self._cookies
        return result

    async def get_nav(self) -> dict[str, Any]:
        return await self._get_json(f"{self.API}/x/web-interface/nav")

    # ------------------------------------------------------------------ 收藏夹
    async def get_folders(self, up_mid: str) -> list[dict[str, Any]]:
        data = await self._get_json(
            f"{self.API}/x/v3/fav/folder/created/list-all",
            params={"up_mid": up_mid},
        )
        folders = list(data.get("list") or [])
        return [
            {
                "fid": str(f.get("id", "")),
                "title": f.get("title", ""),
                "media_count": int(f.get("media_count", 0)),
                "is_watch_later": False,
            }
            for f in folders
        ]

    async def get_watch_later(self) -> list[dict[str, Any]]:
        data = await self._get_json(f"{self.API}/x/v2/history/toview/web")
        videos = list(data.get("list") or [])
        return [self._parse_video(v) for v in videos]

    async def get_folder_videos(
        self, fid: str, page: int = 1, page_size: int = 20
    ) -> dict[str, Any]:
        data = await self._get_json(
            f"{self.API}/x/v3/fav/resource/list",
            params={"media_id": fid, "pn": page, "ps": page_size},
        )
        medias = list((data.get("medias") or []) if isinstance(data, dict) else [])
        return {
            "videos": [self._parse_video(m) for m in medias],
            "total": (
                int(data.get("info", {}).get("media_count", 0)) if isinstance(data, dict) else 0
            ),
        }

    # ------------------------------------------------------------------ 视频 / 分P
    async def get_video_info(self, bvid: str) -> dict[str, Any]:
        data = await self._get_json(f"{self.API}/x/web-interface/view", params={"bvid": bvid})
        return self._parse_video_info(data)

    async def get_video_parts(self, bvid: str) -> list[dict[str, Any]]:
        info = await self.get_video_info(bvid)
        return info["parts"]

    # ------------------------------------------------------------------ 字幕 / 音频
    async def get_subtitle_text(self, bvid: str, cid: int) -> str | None:
        mixin_key = await self._get_wbi()
        params = sign_params({"bvid": bvid, "cid": str(cid)}, mixin_key)
        data = await self._get_json(f"{self.API}/x/player/wbi/v2", params=params)
        subtitles = (data.get("subtitle") or {}).get("subtitles") or []
        if not subtitles:
            return None
        # 优先中文 / AI 字幕
        chosen = next(
            (s for s in subtitles if "zh" in str(s.get("lan", "")).lower()),
            subtitles[0],
        )
        sub_url = chosen.get("subtitle_url")
        if not sub_url:
            return None
        sub_url = sub_url if sub_url.startswith("http") else f"https:{sub_url}"
        resp = await self._request("GET", sub_url)
        body = resp.json().get("body") or []
        return "\n".join(item.get("content", "") for item in body)

    async def download_audio(self, bvid: str, cid: int, dest_dir: str | Path) -> str:
        """下载 DASH 音频流，返回本地文件路径。"""
        mixin_key = await self._get_wbi()
        params = sign_params({"bvid": bvid, "cid": str(cid), "fnval": "16"}, mixin_key)
        data = await self._get_json(f"{self.API}/x/player/wbi/playurl", params=params)
        dash = data.get("dash") or {}
        audios = dash.get("audio") or []
        if not audios:
            raise BilibiliError(-1, "no audio stream available")
        # 选最高质量音频
        audio = max(audios, key=lambda a: int(a.get("id", 0)))
        audio_url = audio.get("baseUrl") or audio.get("base_url")
        if not audio_url:
            raise BilibiliError(-1, "audio url missing")

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out_path = dest / f"{bvid}_{cid}.m4s"
        resp = await self._request(
            "GET", audio_url, headers={"Referer": "https://www.bilibili.com"}
        )
        out_path.write_bytes(resp.content)
        return str(out_path)

    # ------------------------------------------------------------------ 解析
    @staticmethod
    def _parse_video(v: dict[str, Any]) -> dict[str, Any]:
        return {
            "bvid": v.get("bvid", ""),
            "aid": int(v.get("aid", 0)),
            "title": v.get("title", ""),
            "cover_url": v.get("pic", "") or v.get("cover", ""),
            "up_name": (
                v.get("owner", {}).get("name", "") if isinstance(v.get("owner"), dict) else ""
            ),
            "pubdate": v.get("pubdate", 0),
            "duration": int(v.get("duration", 0)),
            "is_collection": bool(v.get("is_series", 0) or v.get("is_collection", 0)),
            "is_invalid": bool(v.get("invalid", 0)),
        }

    @staticmethod
    def _parse_video_info(data: dict[str, Any]) -> dict[str, Any]:
        pages = data.get("pages") or []
        parts = [
            {
                "cid": int(p.get("cid", 0)),
                "page": int(p.get("page", 1)),
                "part_title": p.get("part", ""),
                "duration": int(p.get("duration", 0)),
            }
            for p in pages
        ]
        return {
            "bvid": data.get("bvid", ""),
            "aid": int(data.get("aid", 0)),
            "title": data.get("title", ""),
            "cover_url": data.get("pic", ""),
            "up_name": (
                data.get("owner", {}).get("name", "") if isinstance(data.get("owner"), dict) else ""
            ),
            "pubdate": int(data.get("pubdate", 0)),
            "duration": int(data.get("duration", 0)),
            "is_collection": len(parts) > 1,
            "is_invalid": False,
            "parts": parts,
        }
