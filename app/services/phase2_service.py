from __future__ import annotations

from app.collectors.provider import VideoDataProvider
from app.database import Repository
from app.models import ProviderError


class Phase2Service:
    def __init__(
        self,
        repository: Repository,
        provider: VideoDataProvider,
        max_root_comments: int,
        max_child_comments: int,
    ):
        self.repository = repository
        self.provider = provider
        self.max_root_comments = max_root_comments
        self.max_child_comments = max_child_comments

    async def collect_comments_once(self, bvid: str) -> int:
        video = self.repository.get_video(bvid)
        if not video:
            raise ProviderError("视频不存在，无法采集评论")
        aid = video["aid"]
        if aid is None:
            raise ProviderError("缺少 aid，无法采集评论")
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
        items = await self.provider.fetch_danmaku(bvid, int(cid))
        count = self.repository.insert_danmaku(items)
        self.repository.add_log("INFO", f"弹幕采集完成：{count} 条", bvid=bvid)
        return count
