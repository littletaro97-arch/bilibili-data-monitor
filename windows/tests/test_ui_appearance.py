from datetime import datetime, timedelta
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.ui.dashboard import task_label, task_style
from app.desktop_tray import notification_icon_type


def test_cooldown_display_is_interrupted_without_changing_task_status():
    task = {"status": "running", "cooldown_until": (datetime.now().astimezone() + timedelta(hours=1)).isoformat()}
    assert task_style(task) == "interrupted"
    assert task["status"] == "running"
    task["cooldown_until"] = (datetime.now().astimezone() - timedelta(hours=1)).isoformat()
    assert task_style(task) == "running"
    assert [task_label(s) for s in ["running", "paused", "error", "stopped"]] == ["正常", "中断", "异常", "停止"]


def test_notification_click_uses_default_home_action_and_preserves_other_events(monkeypatch):
    activated, delegated = [], []
    class BaseIcon:
        def __call__(self): activated.append("home")
        def _on_notify(self, wparam, lparam): delegated.append((wparam, lparam))
    monkeypatch.setattr("app.desktop_tray.threading.Thread", lambda target, **kwargs: type("InlineThread", (), {"start": lambda self: target()})())
    icon = notification_icon_type(BaseIcon)()
    icon._on_notify(0, 0x405)
    icon._on_notify(0, (17 << 16) | 0x405)
    icon._on_notify(0, 0x404)  # Timeout must never open the application.
    icon._on_notify(0, 0x205)  # Keep the right-click menu handler.
    assert activated == ["home", "home"]
    assert delegated == [(0, 0x404), (0, 0x205)]


def test_asset_allowlist_and_native_theme_security_boundary():
    app = create_app()
    panel = Mock()
    app.state.desktop_panel = panel
    client = TestClient(app, client=("127.0.0.1", 9000), base_url="http://127.0.0.1")
    assert client.get("/assets/app-icon.png").headers["content-type"] == "image/png"
    assert client.get("/assets/app-icon-original.png").status_code == 404
    assert client.get("/assets/config.toml").status_code == 404
    assert client.post("/desktop/theme", json={"dark": True}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/desktop/theme", json={"dark": "true"}).status_code == 400
    assert client.post("/desktop/theme", json={"dark": False}).json()["applied"]
    panel.set_theme.assert_called_once_with(False)
    remote = TestClient(app, client=("192.168.1.2", 9000), base_url="http://127.0.0.1")
    assert remote.post("/desktop/theme", json={"dark": True}).status_code == 403
