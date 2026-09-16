from __future__ import annotations

from pathlib import Path

from app.config import BASE_DIR, load_settings
from app.security import hash_password


def save_lan_settings(enabled: bool, password: str | None = None) -> None:
    current = load_settings()
    password_hash = current.lan.password_hash
    if password:
        password_hash = hash_password(password)
    if enabled and not password_hash:
        raise ValueError("启用局域网访问前必须设置访问密码")

    _write_settings(current, lan_enabled=enabled, lan_password_hash=password_hash)


def save_launcher_settings(show_console: bool) -> None:
    current = load_settings()
    _write_settings(current, launcher_show_console=show_console)


def _write_settings(
    current,
    *,
    lan_enabled: bool | None = None,
    lan_password_hash: str | None = None,
    launcher_show_console: bool | None = None,
) -> None:
    lan_enabled = current.lan.enabled if lan_enabled is None else lan_enabled
    lan_password_hash = current.lan.password_hash if lan_password_hash is None else lan_password_hash
    launcher_show_console = (
        current.launcher.show_console if launcher_show_console is None else launcher_show_console
    )

    content = f"""[app]
host = "{current.app.host}"
port = {current.app.port}

[crawl]
default_interval = {current.crawl.default_interval}
min_interval = {current.crawl.min_interval}
max_concurrency = {current.crawl.max_concurrency}
max_active_tasks = {current.crawl.max_active_tasks}
global_min_request_interval = {current.crawl.global_min_request_interval}
schedule_jitter_seconds = {current.crawl.schedule_jitter_seconds}
failure_cooldown_seconds = {current.crawl.failure_cooldown_seconds}
global_risk_cooldown_seconds = {current.crawl.global_risk_cooldown_seconds}
timeout = {current.crawl.timeout}
save_raw_json = {str(current.crawl.save_raw_json).lower()}

[report]
output_dir = "{current.report.output_dir}"

[database]
path = "{current.database.path}"

[phase2]
max_root_comments = {current.phase2.max_root_comments}
max_child_comments = {current.phase2.max_child_comments}
comment_min_interval_seconds = {current.phase2.comment_min_interval_seconds}
danmaku_min_interval_seconds = {current.phase2.danmaku_min_interval_seconds}

[lan]
enabled = {str(lan_enabled).lower()}
password_hash = "{lan_password_hash}"
session_cookie = "{current.lan.session_cookie}"

[launcher]
show_console = {str(launcher_show_console).lower()}
"""
    (BASE_DIR / "config.toml").write_text(content, encoding="utf-8")
