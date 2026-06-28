from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.collectors.bilibili_client import BilibiliClient
from app.collectors.provider import BilibiliWebProvider
from app.config import BASE_DIR, settings
from app.database import Database, Repository
from app.logger import logger
from app.services.crawl_service import CrawlService
from app.services.report_service import ReportService
from app.services.phase2_service import Phase2Service
from app.services.task_service import TaskScheduler
from app.services.video_service import VideoService
from app.security import verify_session_token
from app.ui.pages import router


def create_app() -> FastAPI:
    database = Database(settings.database_path)
    database.initialize()
    repository = Repository(database)
    client = BilibiliClient(
        timeout=settings.crawl.timeout,
        min_interval_seconds=settings.crawl.global_min_request_interval,
        repository=repository,
    )
    provider = BilibiliWebProvider(client, save_raw_json=settings.crawl.save_raw_json)
    video_service = VideoService(
        repository,
        provider,
        min_interval=settings.crawl.min_interval,
        default_interval=settings.crawl.default_interval,
        max_active_tasks=settings.crawl.max_active_tasks,
    )
    crawl_service = CrawlService(
        repository,
        provider,
        max_concurrency=settings.crawl.max_concurrency,
        failure_cooldown_seconds=settings.crawl.failure_cooldown_seconds,
        risk_cooldown_seconds=settings.crawl.global_risk_cooldown_seconds,
        schedule_jitter_seconds=settings.crawl.schedule_jitter_seconds,
    )
    report_service = ReportService(
        repository,
        settings.report_output_dir,
        BASE_DIR / "app" / "reports" / "templates",
    )
    scheduler = TaskScheduler(crawl_service)
    phase2_service = Phase2Service(
        repository,
        provider,
        max_root_comments=settings.phase2.max_root_comments,
        max_child_comments=settings.phase2.max_child_comments,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("application startup on %s:%s", settings.app.host, settings.app.port)
        repository.add_log("INFO", "application startup")
        scheduler.start()
        try:
            yield
        finally:
            scheduler.shutdown()
            logger.info("application shutdown")

    app = FastAPI(title="Bilibili Local Analytics", lifespan=lifespan)
    app.state.repository = repository
    app.state.video_service = video_service
    app.state.crawl_service = crawl_service
    app.state.report_service = report_service
    app.state.phase2_service = phase2_service
    app.state.scheduler = scheduler

    @app.middleware("http")
    async def lan_access_guard(request, call_next):
        if not settings.lan.enabled:
            return await call_next(request)
        client_host = request.client.host if request.client else ""
        is_local = client_host in {"127.0.0.1", "::1", "localhost"}
        is_login = request.url.path.startswith("/lan/login")
        if is_local or is_login:
            return await call_next(request)
        cookie = request.cookies.get(settings.lan.session_cookie)
        if verify_session_token(cookie, settings.lan.password_hash):
            return await call_next(request)
        return RedirectResponse("/lan/login", status_code=303)

    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    if settings.lan.enabled and not settings.lan.password_hash:
        raise RuntimeError("LAN access requires a password. Disable LAN or set a password in config.toml.")
    host = "0.0.0.0" if settings.lan.enabled else settings.app.host
    if not settings.lan.enabled and host != "127.0.0.1":
        raise RuntimeError("LAN access is disabled, so the app must listen on 127.0.0.1")
    uvicorn.run("app.main:app", host=host, port=settings.app.port, reload=False)


if __name__ == "__main__":
    main()
