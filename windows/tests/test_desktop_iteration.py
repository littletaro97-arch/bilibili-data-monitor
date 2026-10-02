import asyncio
from datetime import timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.cover import safe_cover_url, local_cover_url
from app.database import Database, Repository, local_now
from app.desktop_tray import DesktopTray
from app.models import VideoInfo, VideoStats
from app.services.crawl_service import CrawlService
from app.collectors.provider import _map_info, _map_stats


@pytest.mark.parametrize("value,expected", [
    ("http://i1.hdslb.com/bfs/archive/cover.jpg", "https://i1.hdslb.com/bfs/archive/cover.jpg"),
    ("https://i0.hdslb.com/cover.jpg", "https://i0.hdslb.com/cover.jpg"),
    ("https://example.com/cover.jpg", None),
    ("https://i0.hdslb.com.evil.example/cover.jpg", None),
    ("https://evil-hdslb.com/cover.jpg", None),
    ("https://user:pass@i0.hdslb.com/cover.jpg", None),
    ("https://i0.hdslb.com:8443/cover.jpg", None),
    ("javascript:alert(1)", None),
    ("data:image/svg+xml,<svg/>", None),
    ("https://127.0.0.1/cover.jpg", None),
    ("https://i0.hdslb.com/ bad.jpg", None),
    ("https://i0.hdslb.com:bad/cover.jpg", None),
    (None, None),
])
def test_cover_url_normalizes_trusted_cdn_and_rejects_hostile_inputs(value, expected):
    assert safe_cover_url(value) == expected


def test_cover_is_retained_by_both_metadata_and_snapshot_mapping():
    payload = {"code": 0, "data": {"pic": "http://i1.hdslb.com/cover.jpg", "stat": {"view": 1}}}
    assert _map_info("BV1xx411c7mD", payload).cover_url == "https://i1.hdslb.com/cover.jpg"
    assert _map_stats("BV1xx411c7mD", payload).cover_url == "https://i1.hdslb.com/cover.jpg"


def repository(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return Repository(db)


def add_task(repo, bvid):
    repo.upsert_video(VideoInfo(bvid=bvid, title="测试视频"))
    return repo.create_task(bvid, 300, min_interval=60, max_active=10)


def service(repo, provider):
    return CrawlService(repo, provider, 2, 600, 1800, 0)


@pytest.mark.asyncio
async def test_tray_collection_preserves_paused_stopped_and_cooldown(tmp_path):
    repo = repository(tmp_path)
    ids = {bv: add_task(repo, bv) for bv in ["BV1xx411c7mD", "BV1yy411c7mD", "BV1zz411c7mD", "BV1aa411c7mD"]}
    repo.set_task_status(ids["BV1yy411c7mD"], "paused")
    repo.set_task_status(ids["BV1zz411c7mD"], "stopped")
    with repo.database.connect() as conn:
        conn.execute("UPDATE crawl_tasks SET cooldown_until=? WHERE bvid=?", ((local_now() + timedelta(minutes=5)).isoformat(), "BV1aa411c7mD"))
    calls = []

    class Provider:
        async def fetch_video_stats(self, bv):
            calls.append(bv)
            return VideoStats(bv, view_count=10, cover_url="http://i1.hdslb.com/new.jpg")

    result = await service(repo, Provider()).collect_running_now()
    assert result == {"total": 1, "success": 1, "failed": 0, "skipped": 2}
    assert calls == ["BV1xx411c7mD"]
    assert repo.get_video(calls[0])["cover_url"] == "https://i1.hdslb.com/new.jpg"
    assert repo.get_task_by_bvid("BV1yy411c7mD")["status"] == "paused"


@pytest.mark.asyncio
async def test_overlapping_tray_and_scheduler_do_not_duplicate_a_snapshot(tmp_path):
    repo = repository(tmp_path)
    add_task(repo, "BV1xx411c7mD")
    entered, release = asyncio.Event(), asyncio.Event()

    class Provider:
        async def fetch_video_stats(self, bv):
            entered.set()
            await release.wait()
            return VideoStats(bv, view_count=1)

    crawl = service(repo, Provider())
    first = asyncio.create_task(crawl.collect_once("BV1xx411c7mD"))
    await entered.wait()
    assert await crawl.collect_once("BV1xx411c7mD") is False
    release.set()
    await first
    assert len(repo.list_snapshots("BV1xx411c7mD")) == 1


@pytest.mark.asyncio
async def test_pausing_during_detection_does_not_restart_task(tmp_path):
    repo = repository(tmp_path)
    task_id = add_task(repo, "BV1xx411c7mD")

    class Provider:
        async def fetch_video_stats(self, bv):
            repo.set_task_status(task_id, "paused")
            return VideoStats(bv, view_count=1)

    await service(repo, Provider()).collect_running_now()
    assert repo.get_task(task_id)["status"] == "paused"


@pytest.mark.asyncio
async def test_missing_cover_does_not_clear_existing_cover(tmp_path):
    repo = repository(tmp_path)
    add_task(repo, "BV1xx411c7mD")
    repo.update_video_cover("BV1xx411c7mD", "https://i0.hdslb.com/old.jpg")

    class Provider:
        async def fetch_video_stats(self, bv):
            return VideoStats(bv, view_count=1)

    await service(repo, Provider()).collect_running_now()
    assert repo.get_video("BV1xx411c7mD")["cover_url"] == "https://i0.hdslb.com/old.jpg"


@pytest.mark.asyncio
async def test_tray_actions_return_to_panel_settings_and_schedule_exit(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("app.desktop_tray.webbrowser.open", opened.append)
    exited = asyncio.Event()
    tray = DesktopTray(asyncio.get_running_loop(), None, 19001, exited.set)
    tray.open_panel()
    tray.open_settings()
    tray.exit_program()
    await asyncio.wait_for(exited.wait(), 1)
    assert opened == ["http://127.0.0.1:19001/", "http://127.0.0.1:19001/settings"]


@pytest.mark.asyncio
async def test_tray_repeated_clicks_do_not_submit_parallel_batches():
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Crawl:
        async def collect_running_now(self):
            calls.append(1)
            started.set()
            await release.wait()
            return {"success": 1, "failed": 0, "skipped": 0}

    tray = DesktopTray(asyncio.get_running_loop(), Crawl(), 19001, lambda: None)
    tray.icon = Mock()
    tray.collect_now()
    await started.wait()
    tray.collect_now()
    release.set()
    await asyncio.wrap_future(tray._pending)
    assert len(calls) == 1
    assert tray.icon.notify.call_count == 1


def test_detail_and_refresh_api_never_render_untrusted_cover(tmp_path):
    from app.main import create_app
    repo = repository(tmp_path)
    repo.upsert_video(VideoInfo("BV1xx411c7mD", title="<script>bad</script>", cover_url="https://evil.example/image.png"))
    app = create_app()
    app.state.repository = repo
    client = TestClient(app)
    response = client.get("/videos/BV1xx411c7mD")
    assert response.status_code == 200
    assert "evil.example" not in response.text
    assert "&lt;script&gt;bad&lt;/script&gt;" in response.text
    assert "暂无封面" in response.text
    assert client.get("/api/videos/BV1xx411c7mD/latest").json()["cover_url"] is None
    repo.update_video_cover("BV1xx411c7mD", "http://i0.hdslb.com/cover.jpg")
    url = local_cover_url("BV1xx411c7mD", "https://i0.hdslb.com/cover.jpg")
    assert f'src="{url}"' in client.get("/videos/BV1xx411c7mD").text
    assert client.get("/api/videos/BV1xx411c7mD/latest").json()["cover_url"] == url
