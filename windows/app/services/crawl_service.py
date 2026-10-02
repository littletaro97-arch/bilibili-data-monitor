from __future__ import annotations

import asyncio
import random

from app.collectors.provider import VideoDataProvider
from app.database import Repository, local_now, parse_iso
from app.cover import safe_cover_url
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
        self._inflight: set[str] = set()

    async def collect_once(self, bvid: str, collection_source: str = "MANUAL", *, running_only: bool = False) -> bool:
        task = self.repository.get_task_by_bvid(bvid)
        if not task or task["status"] == "stopped" or (running_only and task["status"] != "running"):
            return False

        if bvid in self._inflight:
            return False
        self._inflight.add(bvid)
        try:
            return await self._collect_task(task, bvid, collection_source, running_only)
        finally:
            self._inflight.discard(bvid)

    async def _collect_task(self, task, bvid: str, collection_source: str, running_only: bool) -> bool:
        async with self._semaphore:
            current_task = self.repository.get_task_by_bvid(bvid)
            if not current_task or current_task["status"] == "stopped" or (running_only and current_task["status"] != "running"):
                return False
            try:
                stats = await self.provider.fetch_video_stats(bvid)
                cover_url = safe_cover_url(stats.cover_url)
                if cover_url:
                    self.repository.update_video_cover(bvid, cover_url)
                self.repository.insert_snapshot(stats, collection_source=collection_source)
                jitter = random.randint(0, self.schedule_jitter_seconds)
                self.repository.mark_success(bvid, int(task["interval_seconds"]), jitter)
                self.repository.add_log("INFO", "采集成功", bvid=bvid)
                logger.info("collected stats for %s", bvid)
                return True
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

    async def collect_running_now(self) -> dict[str, int]:
        """Tray action: running tasks only, preserving cooldown and paused/error states."""
        tasks = self.repository.list_tasks()
        eligible = []
        now = local_now()
        for task in tasks:
            cooldown = parse_iso(task["cooldown_until"])
            if cooldown is not None and cooldown.tzinfo is None:
                cooldown = cooldown.astimezone()
            if task["status"] == "running" and (cooldown is None or cooldown <= now) and task["bvid"] not in self._inflight:
                eligible.append(task)
        results = await asyncio.gather(
            *(self.collect_once(task["bvid"], collection_source="MANUAL", running_only=True) for task in eligible),
            return_exceptions=True,
        )
        failed = sum(isinstance(result, Exception) for result in results)
        success = sum(result is True for result in results)
        return {"total": success + failed, "success": success, "failed": failed, "skipped": len(tasks) - success - failed}

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
