"""Headless rendering: fresh templates must work even with stale/missing shared CSS.

Opt-in browser checks require the development Playwright runtime; no desktop
window or user browser/profile is opened, and all HTTP requests use TestClient.
"""
import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient


@pytest.mark.skipif(os.environ.get("BILIBILI_MONITOR_HEADLESS_TEST") != "1", reason="opt-in headless development browser")
@pytest.mark.parametrize("shared_css_missing", [False, True])
def test_switch_dimensions_and_interaction_survive_stale_shared_css(tmp_path, shared_css_missing):
    from playwright.sync_api import sync_playwright, expect
    from app.main import create_app
    from app.config import BASE_DIR
    client = TestClient(create_app(), client=("127.0.0.1", 9000), base_url="http://127.0.0.1")
    # Shared appearance now deliberately has no component rules, like an old cache.
    stale_css = (BASE_DIR / "app/assets/appearance.css").read_text(encoding="utf-8")
    assert ".switch-card" not in stale_css

    def respond(route):
        path = urlsplit(route.request.url).path
        if path == "/assets/appearance.css":
            route.fulfill(status=404 if shared_css_missing else 200, content_type="text/css", body="" if shared_css_missing else stale_css)
            return
        assert route.request.method == "GET", "Rendering tests must not save settings"
        response = client.get(path)
        route.fulfill(status=response.status_code, headers={k:v for k,v in response.headers.items() if k.lower() not in {"content-length", "content-encoding"}}, body=response.content)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1150, "height": 800})
            page.route("**/*", respond)
            page.goto("http://127.0.0.1/settings", wait_until="networkidle")
            cards = page.locator(".switch-card")
            assert cards.count() == 4
            for i in range(cards.count()):
                card = cards.nth(i)
                box = card.bounding_box()
                assert 74 <= box["height"] <= 100
                icon = card.locator("svg")
                assert icon.bounding_box()["width"] == 24
                assert icon.bounding_box()["height"] == 24
                assert icon.get_attribute("width") == "24" and icon.get_attribute("fill") == "none"
                track = card.locator(".switch-track")
                assert track.bounding_box()["width"] == 50
                assert track.bounding_box()["height"] == 30
                assert track.evaluate("e => getComputedStyle(e).borderRadius") == "999px"
                assert card.locator("input").evaluate("e => getComputedStyle(e).opacity") == "0"
                assert track.bounding_box()["x"] > card.locator(".switch-title").bounding_box()["x"]
            toggle = page.locator("#show-console")
            original = toggle.is_checked()
            toggle.focus()
            page.keyboard.press("Space")
            assert toggle.is_checked() != original
            page.locator("label[for=show-console] .switch-title").click()
            assert toggle.is_checked() == original
            page.get_by_role("switch", name="显示输入的密码", exact=True).click()
            assert page.locator("#password").get_attribute("type") == "text"
            page.get_by_role("switch", name="显示输入的密码", exact=True).click()
            assert page.locator("#password").get_attribute("type") == "password"
            page.locator("#lan-enabled").check()
            if not shared_css_missing:
                expect(page.locator("#lan-enabled + .switch-track")).to_have_css("background-color", "rgb(48, 105, 99)")
                page.locator("[data-theme-toggle]").click()
                expect(page.locator("#lan-enabled + .switch-track")).to_have_css("background-color", "rgb(120, 211, 196)")
            if not shared_css_missing:
                # Local artifact only; no screenshots of the user's desktop.
                page.locator("[data-theme-toggle]").click()
                expect(page.locator("#lan-enabled + .switch-track")).to_have_css("background-color", "rgb(48, 105, 99)")
                cards.nth(1).screenshot(path=str(tmp_path / "switch-card.png"))
        finally:
            browser.close()
