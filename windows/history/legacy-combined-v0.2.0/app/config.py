from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 7860


@dataclass(frozen=True)
class CrawlConfig:
    default_interval: int = 300
    min_interval: int = 60
    max_concurrency: int = 2
    max_active_tasks: int = 10
    global_min_request_interval: int = 3
    schedule_jitter_seconds: int = 30
    failure_cooldown_seconds: int = 600
    global_risk_cooldown_seconds: int = 1800
    timeout: int = 10
    save_raw_json: bool = False


@dataclass(frozen=True)
class ReportConfig:
    output_dir: str = "reports/output"


@dataclass(frozen=True)
class DatabaseConfig:
    path: str = "data/bilibili_local.db"


@dataclass(frozen=True)
class Phase2Config:
    max_root_comments: int = 500
    max_child_comments: int = 20
    comment_min_interval_seconds: int = 600
    danmaku_min_interval_seconds: int = 600


@dataclass(frozen=True)
class LanConfig:
    enabled: bool = False
    password_hash: str = ""
    session_cookie: str = "blla_lan_auth"


@dataclass(frozen=True)
class LauncherConfig:
    show_console: bool = True


@dataclass(frozen=True)
class Settings:
    app: AppConfig = AppConfig()
    crawl: CrawlConfig = CrawlConfig()
    report: ReportConfig = ReportConfig()
    database: DatabaseConfig = DatabaseConfig()
    phase2: Phase2Config = Phase2Config()
    lan: LanConfig = LanConfig()
    launcher: LauncherConfig = LauncherConfig()

    @property
    def database_path(self) -> Path:
        return _resolve(self.database.path)

    @property
    def report_output_dir(self) -> Path:
        return _resolve(self.report.output_dir)


def _resolve(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path) if path else BASE_DIR / "config.toml"
    raw: dict = {}
    if config_path.exists():
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))

    return Settings(
        app=AppConfig(**raw.get("app", {})),
        crawl=CrawlConfig(**raw.get("crawl", {})),
        report=ReportConfig(**raw.get("report", {})),
        database=DatabaseConfig(**raw.get("database", {})),
        phase2=Phase2Config(**raw.get("phase2", {})),
        lan=LanConfig(**raw.get("lan", {})),
        launcher=LauncherConfig(**raw.get("launcher", {})),
    )


settings = load_settings()
