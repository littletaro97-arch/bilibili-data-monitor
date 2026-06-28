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
enabled = {str(enabled).lower()}
password_hash = "{password_hash}"
session_cookie = "{current.lan.session_cookie}"
"""
    (BASE_DIR / "config.toml").write_text(content, encoding="utf-8")
