from __future__ import annotations

from pathlib import Path

from app.config import BASE_DIR, settings
from app.security import hash_password


def save_lan_settings(enabled: bool, password: str | None = None) -> None:
    password_hash = settings.lan.password_hash
    if password:
        password_hash = hash_password(password)
    if enabled and not password_hash:
        raise ValueError("启用局域网访问前必须设置访问密码")

    content = f"""[app]
host = "{settings.app.host}"
port = {settings.app.port}

[crawl]
default_interval = {settings.crawl.default_interval}
min_interval = {settings.crawl.min_interval}
max_concurrency = {settings.crawl.max_concurrency}
max_active_tasks = {settings.crawl.max_active_tasks}
global_min_request_interval = {settings.crawl.global_min_request_interval}
schedule_jitter_seconds = {settings.crawl.schedule_jitter_seconds}
failure_cooldown_seconds = {settings.crawl.failure_cooldown_seconds}
global_risk_cooldown_seconds = {settings.crawl.global_risk_cooldown_seconds}
timeout = {settings.crawl.timeout}
save_raw_json = {str(settings.crawl.save_raw_json).lower()}

[report]
output_dir = "{settings.report.output_dir}"

[database]
path = "{settings.database.path}"

[phase2]
max_root_comments = {settings.phase2.max_root_comments}
max_child_comments = {settings.phase2.max_child_comments}
comment_min_interval_seconds = {settings.phase2.comment_min_interval_seconds}
danmaku_min_interval_seconds = {settings.phase2.danmaku_min_interval_seconds}

[lan]
enabled = {str(enabled).lower()}
password_hash = "{password_hash}"
session_cookie = "{settings.lan.session_cookie}"
"""
    (BASE_DIR / "config.toml").write_text(content, encoding="utf-8")
