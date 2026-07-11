from __future__ import annotations

import asyncio
import random

from app.collectors.provider import VideoDataProvider
from app.database import Repository
from app.logger import logger
from app.models import ProviderError, RiskControlError


class CrawlService:
    def __init__(
        self,
        repository: Repository,
        provider: VideoDataProvider,
        max_concurrency: int,
        failure_cooldown_seconds: int,
        risk_cooldown_seconds: int,
        schedule_jitter_seconds: int,
    ):
        self.repository = repository
        self.provider = provider
        self.failure_cooldown_seconds = failure_cooldown_seconds
        self.risk_cooldown_seconds = risk_cooldown_seconds
        self.schedule_jitter_seconds = schedule_jitter_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def collect_once(self, bvid: str, collection_source: str = "MANUAL") -> None:
        task = self.repository.get_task_by_bvid(bvid)
        if not task or task["status"] == "stopped":
            return

        async with self._semaphore:
            try:
                stats = await self.provider.fetch_video_stats(bvid)
                self.repository.insert_snapshot(stats, collection_source=collection_source)
                jitter = random.randint(0, self.schedule_jitter_seconds)
                self.repository.mark_success(bvid, int(task["interval_seconds"]), jitter)
                self.repository.add_log("INFO", "采集成功", bvid=bvid)
                logger.info("collected stats for %s", bvid)
            except RiskControlError as exc:
                message = str(exc)
                self.repository.mark_failure(
                    bvid,
                    message,
                    cooldown_seconds=self.risk_cooldown_seconds,
                    force_error=True,
                )
                self.repository.add_log("WARNING", "触发风控或访问限制，任务进入冷却", bvid=bvid, detail=message)
                logger.warning("risk control for %s: %s", bvid, message)
                raise
            except ProviderError as exc:
                message = str(exc)
                self.repository.mark_failure(
                    bvid,
                    message,
                    cooldown_seconds=self.failure_cooldown_seconds,
                )
                self.repository.add_log("ERROR", "采集失败", bvid=bvid, detail=message)
                logger.error("collection failed for %s: %s", bvid, message)
                raise
            except Exception as exc:
                message = f"采集任务异常：{exc}"
                self.repository.mark_failure(
                    bvid,
                    message,
                    cooldown_seconds=self.failure_cooldown_seconds,
                )
                self.repository.add_log("ERROR", "采集任务异常", bvid=bvid, detail=message)
                logger.exception("collection crashed for %s", bvid)
                raise ProviderError(message) from exc

    async def run_due_tasks(self) -> None:
        tasks = self.repository.due_running_tasks()
        if not tasks:
            return
        results = await asyncio.gather(
            *(self.collect_once(task["bvid"], collection_source="AUTO") for task in tasks),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.debug("due task ended with handled exception: %s", result)
