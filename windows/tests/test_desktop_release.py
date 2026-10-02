import asyncio
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.collectors.video_info import resolve_bvid
from app.models import InvalidBvidError, RateLimitError, VideoStats
from app.services.video_service import VideoService
from tests.test_desktop_iteration import repository, add_task, service


@pytest.mark.asyncio
async def test_short_link_redirect_to_bv_without_fetching_destination():
    calls = []
    def redirect(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://www.bilibili.com/video/BV1GJ411x7h7/?share=1"})
    assert await resolve_bvid("分享 https://b23.tv/Test123", transport=httpx.MockTransport(redirect)) == "BV1GJ411x7h7"
    assert calls == ["https://b23.tv/Test123"]


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["http://www.bilibili.com/video/BV1GJ411x7h7", "https://evil.example/BV1GJ411x7h7", "https://127.0.0.1/BV1GJ411x7h7", "https://user:pass@www.bilibili.com/video/BV1GJ411x7h7"])
async def test_short_link_rejects_untrusted_redirect(target):
    with pytest.raises(InvalidBvidError):
        await resolve_bvid("https://b23.tv/Test123", transport=httpx.MockTransport(lambda request: httpx.Response(302, headers={"Location": target})))


@pytest.mark.asyncio
async def test_full_link_does_not_need_network():
    assert await resolve_bvid("https://www.bilibili.com/video/BV1GJ411x7h7", transport=httpx.MockTransport(lambda request: pytest.fail("network called"))) == "BV1GJ411x7h7"


@pytest.mark.asyncio
async def test_recycle_stops_detection_and_restore_preserves_history(tmp_path):
    repo = repository(tmp_path)
    task_id = add_task(repo, "BV1xx411c7mD")
    repo.insert_snapshot(VideoStats("BV1xx411c7mD", view_count=10))
    video = VideoService(repo, None, 60, 300, 10)
    provider = Mock()
    crawl = service(repo, provider)
    video.stop_task(task_id)
    assert not repo.due_running_tasks()
    assert await crawl.collect_once("BV1xx411c7mD") is False
    provider.fetch_video_stats.assert_not_called()
    video.resume_task(task_id)
    assert repo.get_task(task_id)["status"] == "stopped"
    video.restore_task(task_id)
    assert repo.get_task(task_id)["status"] == "running"
    assert repo.latest_snapshot("BV1xx411c7mD")["view_count"] == 10
    assert len(repo.due_running_tasks()) == 1


@pytest.mark.asyncio
async def test_recycling_during_collection_discards_response(tmp_path):
    repo = repository(tmp_path)
    task_id = add_task(repo, "BV1xx411c7mD")
    class Provider:
        async def fetch_video_stats(self, bv):
            repo.set_task_status(task_id, "stopped")
            return VideoStats(bv, view_count=100)
    assert await service(repo, Provider()).collect_once("BV1xx411c7mD") is False
    assert repo.latest_snapshot("BV1xx411c7mD") is None


def test_restore_respects_running_limit(tmp_path):
    repo = repository(tmp_path)
    first = add_task(repo, "BV1xx411c7mD")
    repo.set_task_status(first, "stopped")
    add_task(repo, "BV1GJ411x7h7")
    with pytest.raises(RateLimitError):
        VideoService(repo, None, 60, 300, 1).restore_task(first)
    assert repo.get_task(first)["status"] == "stopped"


def test_recycle_page_restore_and_desktop_activation_guard(tmp_path):
    from app.main import create_app
    repo = repository(tmp_path)
    task_id = add_task(repo, "BV1xx411c7mD")
    repo.set_task_status(task_id, "stopped")
    app = create_app()
    app.state.repository = repo
    app.state.video_service = VideoService(repo, None, 60, 300, 10)
    panel = Mock()
    app.state.desktop_panel = panel
    client = TestClient(app, client=("127.0.0.1", 9999), base_url="http://127.0.0.1")
    assert "取回并恢复检测" in client.get("/recycle-bin").text
    assert client.post(f"/recycle-bin/{task_id}/restore").status_code == 200
    assert repo.get_task(task_id)["status"] == "running"
    assert client.post("/desktop/activate", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/desktop/activate").json()["activated"] is True
    panel.open.assert_called_once_with("/")


def test_panel_close_hides_until_explicit_exit():
    from app.desktop_panel import DesktopPanel
    panel = DesktopPanel.__new__(DesktopPanel)
    panel.window = Mock()
    panel.exiting = False
    assert panel.hide() is False
    assert panel.hidden is True
    panel.window.hide.assert_called_once()
    panel.close()
    assert panel.exiting and panel.hide() is True
