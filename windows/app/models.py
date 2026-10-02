from __future__ import annotations

from dataclasses import dataclass


class AppError(Exception):
    """Base exception shown to users without a traceback."""


class InvalidBvidError(AppError):
    pass


class DuplicateTaskError(AppError):
    pass


class RateLimitError(AppError):
    pass


class ProviderError(AppError):
    pass


class RiskControlError(ProviderError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    bvid: str
    aid: int | None = None
    cid: int | None = None
    title: str | None = None
    owner_mid: int | None = None
    owner_name: str | None = None
    pubdate: int | None = None
    duration: int | None = None
    cover_url: str | None = None
    raw_json: str | None = None


@dataclass(frozen=True)
class VideoStats:
    bvid: str
    view_count: int | None = None
    danmaku_count: int | None = None
    reply_count: int | None = None
    favorite_count: int | None = None
    coin_count: int | None = None
    share_count: int | None = None
    like_count: int | None = None
    online_count: int | None = None
    online_text: str | None = None
    raw_json: str | None = None
    cover_url: str | None = None


@dataclass(frozen=True)
class VideoComment:
    bvid: str
    rpid: str
    parent_rpid: str | None = None
    user_mid: int | None = None
    user_name: str | None = None
    message: str | None = None
    like_count: int | None = None
    reply_count: int | None = None
    ctime: int | None = None
    raw_json: str | None = None


@dataclass(frozen=True)
class DanmakuItem:
    bvid: str
    cid: int | None = None
    progress_sec: float | None = None
    text: str | None = None
    send_time: int | None = None
    raw_text: str | None = None
