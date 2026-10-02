from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import os
import threading
import time
import webbrowser

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.collectors.bilibili_client import BilibiliClient
from app.collectors.provider import BilibiliWebProvider
from app.config import BASE_DIR, RUNTIME_DIR, Settings, settings
from app.database import Database, Repository
from app.cover import CoverCache
from app.desktop_tray import DesktopTray
from app.logger import logger
from app.services.crawl_service import CrawlService
from app.services.export_service import ExportService
from app.services.history_exchange_service import HistoryExchangeService
from app.services.report_service import ReportService
from app.services.phase2_service import Phase2Service
from app.services.task_service import TaskScheduler
from app.services.video_service import VideoService
from app.services.update_service import UpdateService
from app.security import verify_session_token
from app.ui.pages import router, _request_shutdown


def resolve_bind_host(current_settings: Settings = settings) -> str:
    if current_settings.lan.enabled:
        if not current_settings.lan.password_hash:
            raise RuntimeError("LAN access requires a password. Disable LAN or set a password in config.toml.")
        return "0.0.0.0"
    if current_settings.app.host != "127.0.0.1":
        raise RuntimeError("LAN access is disabled, so the app must listen on 127.0.0.1")
    return current_settings.app.host


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
    export_service = ExportService(repository, RUNTIME_DIR / "exports")
    history_exchange_service = HistoryExchangeService(repository)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bind_host = resolve_bind_host(settings)
        logger.info("application startup on %s:%s", bind_host, settings.app.port)
        if settings.lan.enabled:
            logger.warning(
                "LAN access is enabled; service is reachable from the local network on 0.0.0.0:%s. "
                "Disable LAN mode for local-only debugging.",
                settings.app.port,
            )
        repository.add_log("INFO", "application startup")
        scheduler.start()
        panel = getattr(app.state, "desktop_panel", None)
        tray = DesktopTray(asyncio.get_running_loop(), crawl_service, settings.app.port, lambda: _request_shutdown(app), panel.open if panel else None)
        app.state.desktop_tray = tray
        tray.start()
        try:
            yield
        finally:
            tray.stop()
            scheduler.shutdown()
            logger.info("application shutdown")

    app = FastAPI(title="Bilibili Local Analytics", lifespan=lifespan)
    app.state.repository = repository
    app.state.cover_cache = CoverCache(RUNTIME_DIR / "cache" / "covers")
    app.state.video_service = video_service
    app.state.crawl_service = crawl_service
    app.state.report_service = report_service
    app.state.phase2_service = phase2_service
    app.state.export_service = export_service
    app.state.history_exchange_service = history_exchange_service
    app.state.history_exchange_previews = {}
    app.state.scheduler = scheduler
    app.state.update_service = UpdateService(RUNTIME_DIR / "updates")

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


def main(*, desktop: bool = True) -> None:
    host = resolve_bind_host(settings)
    if settings.lan.enabled:
        logger.warning(
            "LAN access is enabled; uvicorn will listen on 0.0.0.0:%s. "
            "Use only on a trusted LAN with a password.",
            settings.app.port,
        )
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=settings.app.port, reload=False))
    app.state.shutdown_callback = lambda: setattr(server, "should_exit", True)
    if desktop and os.name == "nt":
        from app.desktop_panel import DesktopPanel, evergreen_installed, missing_runtime_notice
        if evergreen_installed():
            try:
                panel = DesktopPanel(settings.app.port)
            except ImportError:
                logger.exception("自有窗口依赖缺失，将使用浏览器面板")
            else:
                app.state.desktop_panel = panel
                panel.run(server)
                return
        else:
            missing_runtime_notice()
        def open_browser():
            for _ in range(200):
                if server.started:
                    webbrowser.open(f"http://127.0.0.1:{settings.app.port}/")
                    return
                if server.should_exit:
                    return
                time.sleep(.1)
        threading.Thread(target=open_browser, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
