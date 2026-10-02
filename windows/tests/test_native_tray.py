"""Opt-in integration test: creates and removes a real Windows notification icon."""
import asyncio
import os

import pytest

from app.desktop_tray import DesktopTray
from app.database import Database, Repository
from app.models import VideoInfo, VideoStats
from app.services.crawl_service import CrawlService


@pytest.mark.skipif(os.name != "nt" or os.environ.get("BILIBILI_MONITOR_NATIVE_TEST") != "1", reason="requires explicit Windows desktop integration run")
@pytest.mark.asyncio
async def test_native_icon_lifecycle_and_actual_menu_callbacks(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("app.desktop_tray.webbrowser.open", opened.append)
    repo = Repository(Database(tmp_path / "test.db"))
    repo.database.initialize()
    repo.upsert_video(VideoInfo("BV1xx411c7mD"))
    repo.create_task("BV1xx411c7mD", 300, 60, 10)

    class Provider:
        async def fetch_video_stats(self, bv):
            return VideoStats(bv, view_count=7)

    crawl = CrawlService(repo, Provider(), 2, 600, 1800, 0)
    exited = asyncio.Event()
    tray = DesktopTray(asyncio.get_running_loop(), crawl, 18769, exited.set)
    tray.start()
    try:
        for _ in range(100):
            if tray.icon is not None and tray.icon.visible:
                break
            await asyncio.sleep(.05)
        assert tray.icon is not None and tray.icon.visible
        assert tray.thread.is_alive()
        # Invoke the real pystray default action and menu callbacks, with no browser side effects.
        tray.icon()
        items = list(tray.icon.menu)
        items[2](tray.icon)
        assert opened == ["http://127.0.0.1:18769/", "http://127.0.0.1:18769/settings"]
        items[1](tray.icon)
        await asyncio.wrap_future(tray._pending)
        assert repo.latest_snapshot("BV1xx411c7mD")["view_count"] == 7
        items[-1](tray.icon)
        await asyncio.wait_for(exited.wait(), 1)
    finally:
        tray.stop()
    assert not tray.thread.is_alive()
    assert not tray.icon.visible
