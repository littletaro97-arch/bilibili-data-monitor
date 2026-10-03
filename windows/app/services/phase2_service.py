from __future__ import annotations

import time

from app.collectors.provider import VideoDataProvider
from app.database import Repository
from app.models import DanmakuItem, ProviderError, VideoComment


class Phase2Service:
    def __init__(
        self,
        repository: Repository,
        provider: VideoDataProvider,
        max_root_comments: int,
        max_child_comments: int,
        comment_min_interval_seconds: int = 600,
        danmaku_min_interval_seconds: int = 600,
    ):
        self.repository = repository
        self.provider = provider
        self.max_root_comments = max_root_comments
        self.max_child_comments = max_child_comments
        self._intervals = {"评论": comment_min_interval_seconds, "弹幕": danmaku_min_interval_seconds}
        self._last_attempt = {}

    def _reserve_attempt(self, kind):
        now = time.monotonic()
        previous = self._last_attempt.get(kind)
        interval = max(60, self._intervals[kind])
        if previous is not None and now - previous < interval:
            raise ProviderError(f"{kind}采集请稍后重试，剩余 {int(interval - (now - previous)) + 1} 秒")
        # Reserve before awaiting: concurrent clicks and failed requests also cool down.
        self._last_attempt[kind] = now

    async def collect_comments_once(self, bvid: str) -> int:
        video = self.repository.get_video(bvid)
        if not video:
            raise ProviderError("视频不存在，无法采集评论")
        aid = video["aid"]
        if aid is None:
            raise ProviderError("缺少 aid，无法采集评论")
        self._reserve_attempt("评论")
        comments = await self.provider.fetch_comments(
            bvid,
            int(aid),
            max_root=self.max_root_comments,
            max_child=self.max_child_comments,
        )
        count = self.repository.insert_comments(comments)
        self.repository.add_log("INFO", f"评论采集完成：{count} 条", bvid=bvid)
        return count

    async def collect_danmaku_once(self, bvid: str) -> int:
        video = self.repository.get_video(bvid)
        if not video:
            raise ProviderError("视频不存在，无法采集弹幕")
        cid = video["cid"]
        if cid is None:
            raise ProviderError("缺少 cid，无法采集弹幕")
        self._reserve_attempt("弹幕")
        items = await self.provider.fetch_danmaku(bvid, int(cid))
        count = self.repository.insert_danmaku(items)
        self.repository.add_log("INFO", f"弹幕采集完成：{count} 条", bvid=bvid)
        return count

    def import_comments_text(self, bvid: str, text: str) -> int:
        lines = _non_empty_lines(text)
        comments = [
            VideoComment(
                bvid=bvid,
                rpid=f"local-comment-{index + 1}",
                user_name="本地导入",
                message=line,
                like_count=0,
                reply_count=0,
            )
            for index, line in enumerate(lines)
        ]
        count = self.repository.insert_comments(comments)
        self.repository.add_log("INFO", f"本地导入评论：{count} 条", bvid=bvid)
        return count

    def import_danmaku_text(self, bvid: str, text: str) -> int:
        video = self.repository.get_video(bvid)
        cid = int(video["cid"]) if video and video["cid"] is not None else None
        items: list[DanmakuItem] = []
        for index, line in enumerate(_non_empty_lines(text)):
            progress_sec, content = _parse_danmaku_line(line, fallback_seconds=index * 5.0)
            items.append(
                DanmakuItem(
                    bvid=bvid,
                    cid=cid,
                    progress_sec=progress_sec,
                    text=content,
                    send_time=None,
                    raw_text=line,
                )
            )
        count = self.repository.insert_danmaku(items)
        self.repository.add_log("INFO", f"本地导入弹幕：{count} 条", bvid=bvid)
        return count

    def seed_demo_data(self, bvid: str) -> tuple[int, int]:
        comments = [
            "这个视频节奏很好，讲解很清楚",
            "数据分析部分很有用，希望继续更新",
            "这个工具适合本地观察趋势",
            "讲解清楚，案例很好",
            "希望增加更多本地分析功能",
        ]
        danmaku = [
            "1.5,开头来了",
            "8.0,这个地方很好",
            "15.0,讲解清楚",
            "22.0,数据分析有用",
            "35.0,这里弹幕很密集",
            "38.0,这里弹幕很密集",
            "42.0,继续更新",
        ]
        return self.import_comments_text(bvid, "\n".join(comments)), self.import_danmaku_text(bvid, "\n".join(danmaku))


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_danmaku_line(line: str, fallback_seconds: float) -> tuple[float, str]:
    for separator in [",", "，", "\t"]:
        if separator in line:
            left, right = line.split(separator, 1)
            try:
                return max(0.0, float(left.strip())), right.strip()
            except ValueError:
                break
    return fallback_seconds, line
