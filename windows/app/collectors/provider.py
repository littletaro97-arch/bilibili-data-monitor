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

    async def fetch_danmaku_parts(self, bvid: str) -> list[dict]:
        return []


class BilibiliWebProvider(VideoDataProvider):
    """Fixed public webpage data source. No fallback endpoints are attempted."""

    VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
    ONLINE_TOTAL_URL = "https://api.bilibili.com/x/player/online/total"
    DANMAKU_URL = "https://comment.bilibili.com/{cid}.xml"
    COMMENTS_URL = "https://api.bilibili.com/x/v2/reply"

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
        limit = min(20, max(0, max_root))
        if not limit:
            return []
        data = _require_success(await self.client.get_json(self.COMMENTS_URL,
            {"type": 1, "oid": aid, "pn": 1, "ps": limit, "sort": 2}))
        replies = data.get("replies") or []
        if not isinstance(replies, list):
            raise ProviderError("评论响应结构异常")
        comments = []
        seen = set()
        def append(reply, parent=None):
            if not isinstance(reply, dict):
                return
            rpid = str(reply.get("rpid_str") or reply.get("rpid") or "")
            content = reply.get("content") or {}
            member = reply.get("member") or {}
            message = content.get("message") if isinstance(content, dict) else None
            if not rpid or rpid in seen or not isinstance(message, str) or not message.strip():
                return
            seen.add(rpid)
            comments.append(VideoComment(bvid=bvid, rpid=rpid, parent_rpid=parent,
                user_mid=_as_int(member.get("mid")) if isinstance(member, dict) else None,
                user_name=member.get("uname") if isinstance(member, dict) else None,
                message=message, like_count=_as_int(reply.get("like")),
                reply_count=_as_int(reply.get("rcount")), ctime=_as_int(reply.get("ctime"))))
        for reply in replies[:limit]:
            append(reply)
            if not isinstance(reply, dict):
                continue
            children = reply.get("replies") or []
            if isinstance(children, list):
                for child in children[:min(5, max(0, max_child))]:
                    append(child, str(reply.get("rpid_str") or reply.get("rpid") or ""))
        return comments

    async def fetch_danmaku(self, bvid: str, cid: int) -> list[DanmakuItem]:
        xml_text = await self.client.get_text(self.DANMAKU_URL.format(cid=cid))
        if len(xml_text) > 8 * 1024 * 1024 or "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
            raise ProviderError("弹幕响应过大或包含不支持的 XML 声明")
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ProviderError("弹幕接口未返回有效 XML") from exc
        if root.tag != "i":
            raise ProviderError("弹幕接口返回结构异常")
        items: list[DanmakuItem] = []
        for node in root.findall(".//d"):
            if not node.text or not node.text.strip():
                continue
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
                    source_id=parts[7] if len(parts) > 7 and parts[7].isdigit() else None,
                )
            )
            if len(items) >= 10000:
                break
        return items

    async def fetch_danmaku_parts(self, bvid: str) -> list[dict]:
        data = _require_success(await self.client.get_json(self.VIEW_URL, {"bvid": bvid}))
        pages = data.get("pages") or []
        if not isinstance(pages, list):
            raise ProviderError("视频分 P 信息异常")
        return [{"cid": int(page["cid"]), "page": page.get("page"), "name": page.get("part") or "", "duration": page.get("duration")}
            for page in pages if isinstance(page, dict) and _as_int(page.get("cid")) is not None]


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
