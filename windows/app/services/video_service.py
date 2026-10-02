from __future__ import annotations

import sqlite3

from app.collectors.provider import VideoDataProvider
from app.collectors.video_info import resolve_bvid
from app.database import Repository
from app.logger import logger
from app.models import DuplicateTaskError, RateLimitError


class VideoService:
    def __init__(
        self,
        repository: Repository,
        provider: VideoDataProvider,
        min_interval: int,
        default_interval: int,
        max_active_tasks: int,
    ):
        self.repository = repository
        self.provider = provider
        self.min_interval = min_interval
        self.default_interval = default_interval
        self.max_active_tasks = max_active_tasks

    async def add_video_task(self, text: str, interval_seconds: int | None = None) -> str:
        bvid = await resolve_bvid(text)
        interval = interval_seconds or self.default_interval
        if interval < self.min_interval:
            raise RateLimitError(f"采集间隔不得低于 {self.min_interval} 秒")

        info = await self.provider.fetch_video_info(bvid)
        self.repository.upsert_video(info)
        try:
            self.repository.create_task(
                bvid,
                interval,
                min_interval=self.min_interval,
                max_active=self.max_active_tasks,
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTaskError("该视频任务已存在，不会重复创建") from exc

        self.repository.add_log("INFO", "添加视频任务", bvid=bvid)
        logger.info("added task for %s", bvid)
        return bvid

    def pause_task(self, task_id: int) -> None:
        task = self.repository.get_task(task_id)
        if not task or task["status"] == "stopped":
            return
        self.repository.set_task_status(task_id, "paused")
        self._log_task_action(task_id, "暂停任务")

    def resume_task(self, task_id: int) -> None:
        task = self.repository.get_task(task_id)
        if not task or task["status"] == "stopped":
            return
        if self.repository.count_active_tasks() >= self.max_active_tasks and task["status"] != "running":
            raise RateLimitError(f"第一版最多允许 {self.max_active_tasks} 个 running 任务")
        self.repository.set_task_status(task_id, "running")
        self._log_task_action(task_id, "恢复任务")

    def stop_task(self, task_id: int) -> None:
        self.repository.set_task_status(task_id, "stopped")
        self._log_task_action(task_id, "放入回收站，停止检测")

    def restore_task(self, task_id: int) -> None:
        task = self.repository.get_task(task_id)
        if not task or task["status"] != "stopped":
            return
        self.repository.create_task(task["bvid"], task["interval_seconds"], self.min_interval, self.max_active_tasks)
        self._log_task_action(task_id, "从回收站取回，恢复检测")

    def _log_task_action(self, task_id: int, message: str) -> None:
        task = self.repository.get_task(task_id)
        bvid = task["bvid"] if task else None
        self.repository.add_log("INFO", message, bvid=bvid)
        logger.info("%s: %s", message, bvid)
