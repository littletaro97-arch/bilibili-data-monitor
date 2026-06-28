from __future__ import annotations

import re

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
