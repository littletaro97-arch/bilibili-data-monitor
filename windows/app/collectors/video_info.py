from __future__ import annotations

import re
from urllib.parse import urlsplit
import httpx

from app.models import InvalidBvidError


BVID_RE = re.compile(r"(?<![0-9A-Za-z])(BV[0-9A-Za-z]{10})(?![0-9A-Za-z])")


def parse_bvid(text: str) -> str:
    """Parse a Bilibili BV id from plain input or a video URL."""
    candidate = (text or "").strip()
    if not candidate:
        raise InvalidBvidError("输入不能为空")

    match = BVID_RE.search(candidate)
    if not match:
        raise InvalidBvidError("未识别到合法 BV 号")
    return match.group(1)


async def resolve_bvid(text: str, *, transport=None) -> str:
    try:
        return parse_bvid(text)
    except InvalidBvidError:
        match = re.search(r"(?<![\w./])(?:https?://)?b23\.tv/([A-Za-z0-9]+)(?![\w/])", text or "")
        if not match:
            raise InvalidBvidError("未识别到 BV 号、视频链接或 b23.tv 短链")
    url = f"https://b23.tv/{match[1]}"
    try:
        async with httpx.AsyncClient(timeout=15, transport=transport, follow_redirects=False) as client:
            for _ in range(5):
                parsed = urlsplit(url)
                host = parsed.hostname or ""
                if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443} or not (
                    host == "b23.tv" or host == "bilibili.com" or host.endswith(".bilibili.com")
                ):
                    raise InvalidBvidError("短链跳转到不支持的地址")
                if host != "b23.tv":
                    return parse_bvid(url)
                response = await client.get(url)
                if not response.is_redirect or response.next_request is None:
                    raise InvalidBvidError("短链没有跳转到有效视频，请使用完整视频链接")
                url = str(response.next_request.url)
    except (httpx.HTTPError, ValueError) as exc:
        raise InvalidBvidError("短链解析失败，请检查网络或使用完整视频链接") from exc
    raise InvalidBvidError("短链跳转次数过多")
