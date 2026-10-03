import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient


@pytest.mark.skipif(os.environ.get("BILIBILI_MONITOR_HEADLESS_TEST") != "1", reason="opt-in headless rendering")
def test_time_motion_nested_panels_navigation_and_reduced_motion(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    from app.main import create_app
    from app.database import Database, Repository
    from app.models import VideoInfo, VideoStats
    db = Database(tmp_path / "detail.db")
    db.initialize()
    repo = Repository(db)
    bvid = "BV1xx411c7mD"
    repo.upsert_video(VideoInfo(bvid, title="Motion test"))
    repo.insert_snapshot(VideoStats(bvid, view_count=10), captured_at="2026-10-03T20:41:28.716425+08:00")
    app = create_app()
    app.state.repository = repo
    client = TestClient(app, client=("127.0.0.1", 9000), base_url="http://127.0.0.1")
    def route(request):
        response = client.get(urlsplit(request.request.url).path)
        request.fulfill(status=response.status_code, headers={k:v for k,v in response.headers.items() if k.lower() not in {"content-length", "content-encoding"}}, body=response.content)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width":1280,"height":900})
            page.route("**/*", route)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1/videos/{bvid}")
            time = page.locator('[data-latest-field="captured_at"]')
            assert time.inner_text() == "2026-10-03 20:41"
            assert time.get_attribute("title").endswith("+08:00")
            assert time.evaluate("e => getComputedStyle(e).whiteSpace") == "nowrap"
            assert page.evaluate("formatLatestValue('captured_at','2026-10-03T20:41:28.716425+08:00')") == "2026-10-03 20:41"
            panel = page.locator('details[data-chart-panel="single"]')
            summary = panel.locator(':scope > summary')
            summary.click()
            expect(panel).to_have_attribute("open", "")
            page.wait_for_function("document.querySelector('details[data-chart-panel=single] > .details-body').getAnimations().length === 0")
            nested = panel.locator('details').first
            nested.locator(':scope > summary').click()
            expect(nested).to_have_attribute("open", "")
            summary.click()
            page.wait_for_function("!document.querySelector('details[data-chart-panel=single]').open")
            # Rapid toggles must not leave a permanent height or clipping style.
            summary.click()
            summary.click()
            page.wait_for_function("!document.querySelector('details[data-chart-panel=single]').open")
            assert panel.locator(':scope > .details-body').evaluate("e => e.style.overflow") == ""
            page.locator('nav a[href="/settings"]').click()
            page.wait_for_url("**/settings")
            page.locator('nav a[href="/recycle-bin"]').click()
            page.wait_for_url("**/recycle-bin")
            page.get_by_role("link", name="返回首页", exact=True).click()
            page.wait_for_url("http://127.0.0.1/")
            page.emulate_media(reduced_motion="reduce")
            page.goto("http://127.0.0.1/settings")
            assert page.locator("main").evaluate("e => e.getAnimations().length") == 0
            page.locator('details summary').first.click()
            assert page.locator('.details-body').first.evaluate("e => e.getAnimations().length") == 0
            page.set_viewport_size({"width":390,"height":844})
            page.goto(f"http://127.0.0.1/videos/{bvid}")
            assert page.locator('.metric-time').evaluate("e => e.scrollWidth <= e.clientWidth")
            assert not errors
        finally:
            browser.close()
