from __future__ import annotations

from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from app.collectors.bilibili_client import BilibiliClient
from app.config import BASE_DIR
from app.cover import safe_cover_url
from app.models import DanmakuItem, ProviderError, RiskControlError, VideoComment, VideoInfo, VideoStats


class VideoDataProvider(ABC):
    @abstractmethod
    async def fetch_video_info(self, bvid: str) -> VideoInfo:
        raise NotImplementedError

    @abstractmethod
    async def fetch_video_stats(self, bvid: str) -> VideoStats:
        raise NotImplementedError

    async def fetch_comments(self, bvid: str, aid: int, max_root: int, max_child: int) -> list[VideoComment]:
        raise NotImplementedError

    async def fetch_danmaku(self, bvid: str, cid: int) -> list[DanmakuItem]:
        raise NotImplementedError


class BilibiliWebProvider(VideoDataProvider):
    """Fixed public webpage data source. No fallback endpoints are attempted."""

    VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
    ONLINE_TOTAL_URL = "https://api.bilibili.com/x/player/online/total"
    DANMAKU_URL = "https://comment.bilibili.com/{cid}.xml"

    def __init__(self, client: BilibiliClient, save_raw_json: bool = False):
        self.client = client
        self.save_raw_json = save_raw_json

    async def fetch_video_info(self, bvid: str) -> VideoInfo:
        payload = await self.client.get_json(self.VIEW_URL, {"bvid": bvid})
        data = _require_success(payload)
        owner = data.get("owner") or {}
        return VideoInfo(
            bvid=bvid,
            aid=_as_int(data.get("aid")),
            cid=_as_int(data.get("cid")),
            title=data.get("title"),
            owner_mid=_as_int(owner.get("mid")),
            owner_name=owner.get("name"),
            pubdate=_as_int(data.get("pubdate")),
            duration=_as_int(data.get("duration")),
            cover_url=safe_cover_url(data.get("pic")),
            raw_json=json.dumps(payload, ensure_ascii=False) if self.save_raw_json else None,
        )

    async def fetch_video_stats(self, bvid: str) -> VideoStats:
        payload = await self.client.get_json(self.VIEW_URL, {"bvid": bvid})
        data = _require_success(payload)
        stat = data.get("stat") or {}
        online_payload = await self._fetch_online_total(bvid, data)
        online_text, online_count = _extract_online_display(data, online_payload)
        return VideoStats(
            bvid=bvid,
            view_count=_as_int(stat.get("view")),
            danmaku_count=_as_int(stat.get("danmaku")),
            reply_count=_as_int(stat.get("reply")),
            favorite_count=_as_int(stat.get("favorite")),
            coin_count=_as_int(stat.get("coin")),
            share_count=_as_int(stat.get("share")),
            like_count=_as_int(stat.get("like")),
            online_count=online_count,
            online_text=online_text,
            cover_url=safe_cover_url(data.get("pic")),
            raw_json=json.dumps(payload, ensure_ascii=False) if self.save_raw_json else None,
        )

    async def _fetch_online_total(self, bvid: str, data: dict[str, Any]) -> dict[str, Any] | None:
        aid = _as_int(data.get("aid"))
        cid = _as_int(data.get("cid"))
        if aid is None or cid is None:
            return None
        try:
            return await self.client.get_json(self.ONLINE_TOTAL_URL, {"bvid": bvid, "aid": aid, "cid": cid})
        except RiskControlError:
            raise
        except ProviderError:
            return None

    async def fetch_comments(self, bvid: str, aid: int, max_root: int, max_child: int) -> list[VideoComment]:
        raise ProviderError("第二版评论真实采集未启用：文档未指定稳定公开评论数据源，不能临时拼接接口")

    async def fetch_danmaku(self, bvid: str, cid: int) -> list[DanmakuItem]:
        xml_text = await self.client.get_text(self.DANMAKU_URL.format(cid=cid))
        root = ET.fromstring(xml_text)
        items: list[DanmakuItem] = []
        for node in root.findall(".//d"):
            p = node.attrib.get("p", "")
            parts = p.split(",")
            progress_sec = _as_float(parts[0]) if len(parts) > 0 else None
            send_time = _as_int(parts[4]) if len(parts) > 4 else None
            items.append(
                DanmakuItem(
                    bvid=bvid,
                    cid=cid,
                    progress_sec=progress_sec,
                    text=node.text or "",
                    send_time=send_time,
                    raw_text=None,
                )
            )
        return items


class MockVideoDataProvider(VideoDataProvider):
    def __init__(self, response_path: str | Path | None = None, save_raw_json: bool = False):
        self.response_path = Path(response_path) if response_path else BASE_DIR / "app" / "sample_responses" / "video_view_success.json"
        self.save_raw_json = save_raw_json

    async def fetch_video_info(self, bvid: str) -> VideoInfo:
        payload = json.loads(self.response_path.read_text(encoding="utf-8"))
        payload["data"]["bvid"] = bvid
        return _map_info(bvid, payload, self.save_raw_json)

    async def fetch_video_stats(self, bvid: str) -> VideoStats:
        payload = json.loads(self.response_path.read_text(encoding="utf-8"))
        payload["data"]["bvid"] = bvid
        return _map_stats(bvid, payload, self.save_raw_json)

    async def fetch_comments(self, bvid: str, aid: int, max_root: int, max_child: int) -> list[VideoComment]:
        return [
            VideoComment(
                bvid=bvid,
                rpid="1001",
                user_mid=2001,
                user_name="Mock Commenter",
                message="Mock comment <unsafe>",
                like_count=12,
                reply_count=0,
                ctime=1710000001,
            )
        ][:max_root]

    async def fetch_danmaku(self, bvid: str, cid: int) -> list[DanmakuItem]:
        return [
            DanmakuItem(
                bvid=bvid,
                cid=cid,
                progress_sec=1.2,
                text="Mock danmaku <unsafe>",
                send_time=1710000002,
            )
        ]


def _require_success(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("code") != 0:
        raise ProviderError(f"接口返回失败：code={payload.get('code')}, message={payload.get('message')}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ProviderError("接口响应结构异常：缺少 data")
    return data


def _map_info(bvid: str, payload: dict[str, Any], save_raw_json: bool = False) -> VideoInfo:
    data = _require_success(payload)
    owner = data.get("owner") or {}
    return VideoInfo(
        bvid=bvid,
        aid=_as_int(data.get("aid")),
        cid=_as_int(data.get("cid")),
        title=data.get("title"),
        owner_mid=_as_int(owner.get("mid")),
        owner_name=owner.get("name"),
        pubdate=_as_int(data.get("pubdate")),
        duration=_as_int(data.get("duration")),
        cover_url=safe_cover_url(data.get("pic")),
        raw_json=json.dumps(payload, ensure_ascii=False) if save_raw_json else None,
    )


def _map_stats(bvid: str, payload: dict[str, Any], save_raw_json: bool = False) -> VideoStats:
    data = _require_success(payload)
    stat = data.get("stat") or {}
    online_text, online_count = _extract_online_display(data)
    return VideoStats(
        bvid=bvid,
        view_count=_as_int(stat.get("view")),
        danmaku_count=_as_int(stat.get("danmaku")),
        reply_count=_as_int(stat.get("reply")),
        favorite_count=_as_int(stat.get("favorite")),
        coin_count=_as_int(stat.get("coin")),
        share_count=_as_int(stat.get("share")),
        like_count=_as_int(stat.get("like")),
        online_count=online_count,
        online_text=online_text,
        cover_url=safe_cover_url(data.get("pic")),
        raw_json=json.dumps(payload, ensure_ascii=False) if save_raw_json else None,
    )


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_online_display(data: dict[str, Any], online_payload: dict[str, Any] | None = None) -> tuple[str | None, int | None]:
    if online_payload and online_payload.get("code") == 0:
        online_data = online_payload.get("data") or {}
        total = online_data.get("total")
        count = _as_int(online_data.get("count"))
        if total is not None:
            text = str(total)
            return text, _as_int(text.replace("+", "")) or count
        if count is not None:
            return str(count), count
    count = _extract_online_count(data)
    return (str(count), count) if count is not None else (None, None)


def _extract_online_count(data: dict[str, Any]) -> int | None:
    stat = data.get("stat") or {}
    for source in (data, stat):
        for key in ("online_count", "online", "current_viewers", "now_viewers"):
            value = _as_int(source.get(key))
            if value is not None:
                return value
    return None
