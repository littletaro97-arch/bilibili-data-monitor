from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tzlocal import get_localzone

from app.services.crawl_service import CrawlService


class TaskScheduler:
    def __init__(self, crawl_service: CrawlService):
        self.crawl_service = crawl_service
        self.scheduler = AsyncIOScheduler(timezone=get_localzone())

    def start(self) -> None:
        if self.scheduler.running:
            return
        self.scheduler.add_job(
            self.crawl_service.run_due_tasks,
            "interval",
            seconds=10,
            id="run_due_crawl_tasks",
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
