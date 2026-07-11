from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from app.models import DanmakuItem, RateLimitError, VideoComment, VideoInfo, VideoStats


def local_now() -> datetime:
    return datetime.now().astimezone()


def iso_now() -> str:
    return local_now().isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid TEXT NOT NULL UNIQUE,
                    aid INTEGER,
                    cid INTEGER,
                    title TEXT,
                    owner_mid INTEGER,
                    owner_name TEXT,
                    pubdate INTEGER,
                    duration INTEGER,
                    cover_url TEXT,
                    raw_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS crawl_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'running',
                    interval_seconds INTEGER NOT NULL DEFAULT 300,
                    next_run_at TEXT,
                    last_run_at TEXT,
                    last_success_at TEXT,
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    cooldown_until TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (bvid) REFERENCES videos(bvid)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status_next_run
                ON crawl_tasks(status, next_run_at);

                CREATE TABLE IF NOT EXISTS video_stats_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    view_count INTEGER,
                    danmaku_count INTEGER,
                    reply_count INTEGER,
                    favorite_count INTEGER,
                    coin_count INTEGER,
                    share_count INTEGER,
                    like_count INTEGER,
                    online_count INTEGER,
                    online_text TEXT,
                    source_type TEXT NOT NULL DEFAULT 'collected',
                    source_note TEXT,
                    collection_source TEXT NOT NULL DEFAULT 'UNKNOWN',
                    exchange_digest TEXT,
                    raw_json TEXT,
                    FOREIGN KEY (bvid) REFERENCES videos(bvid)
                );

                CREATE INDEX IF NOT EXISTS idx_stats_bvid_time
                ON video_stats_snapshot(bvid, captured_at);

                CREATE TABLE IF NOT EXISTS crawl_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid TEXT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid TEXT NOT NULL,
                    rpid TEXT NOT NULL,
                    parent_rpid TEXT,
                    user_mid INTEGER,
                    user_name TEXT,
                    message TEXT,
                    like_count INTEGER,
                    reply_count INTEGER,
                    ctime INTEGER,
                    captured_at TEXT NOT NULL,
                    raw_json TEXT,
                    UNIQUE(bvid, rpid)
                );

                CREATE INDEX IF NOT EXISTS idx_comments_bvid_time
                ON comments(bvid, captured_at);

                CREATE TABLE IF NOT EXISTS danmaku (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid TEXT NOT NULL,
                    cid INTEGER,
                    progress_sec REAL,
                    text TEXT,
                    send_time INTEGER,
                    captured_at TEXT NOT NULL,
                    raw_text TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_danmaku_bvid_time
                ON danmaku(bvid, captured_at);
                """
            )
            _ensure_column(conn, "video_stats_snapshot", "source_type", "TEXT NOT NULL DEFAULT 'collected'")
            _ensure_column(conn, "video_stats_snapshot", "source_note", "TEXT")
            _ensure_column(conn, "video_stats_snapshot", "online_count", "INTEGER")
            _ensure_column(conn, "video_stats_snapshot", "online_text", "TEXT")
            _ensure_column(conn, "video_stats_snapshot", "collection_source", "TEXT NOT NULL DEFAULT 'UNKNOWN'")
            _ensure_column(conn, "video_stats_snapshot", "exchange_digest", "TEXT")
            conn.execute("PRAGMA user_version = 1")


class Repository:
    def __init__(self, database: Database):
        self.database = database

    def upsert_video(self, info: VideoInfo) -> None:
        now = iso_now()
        with self.database.connect() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                    bvid, aid, cid, title, owner_mid, owner_name, pubdate,
                    duration, cover_url, raw_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bvid) DO UPDATE SET
                    aid=excluded.aid,
                    cid=excluded.cid,
                    title=excluded.title,
                    owner_mid=excluded.owner_mid,
                    owner_name=excluded.owner_name,
                    pubdate=excluded.pubdate,
                    duration=excluded.duration,
                    cover_url=excluded.cover_url,
                    raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """,
                (
                    info.bvid,
                    info.aid,
                    info.cid,
                    info.title,
                    info.owner_mid,
                    info.owner_name,
                    info.pubdate,
                    info.duration,
                    info.cover_url,
                    info.raw_json,
                    now,
                    now,
                ),
            )

    def create_task(self, bvid: str, interval_seconds: int, min_interval: int, max_active: int) -> int:
        if interval_seconds < min_interval:
            raise RateLimitError(f"采集间隔不得低于 {min_interval} 秒")
        if self.count_active_tasks() >= max_active:
            raise RateLimitError(f"第一版最多允许 {max_active} 个 running 任务")
        now = iso_now()
        with self.database.connect() as conn:
            existing = conn.execute(
                "SELECT id, status FROM crawl_tasks WHERE bvid = ?",
                (bvid,),
            ).fetchone()
            if existing:
                if existing["status"] == "stopped":
                    conn.execute(
                        """
                        UPDATE crawl_tasks
                        SET status='running', interval_seconds=?, next_run_at=?,
                            last_error=NULL, cooldown_until=NULL, updated_at=?
                        WHERE id=?
                        """,
                        (interval_seconds, now, now, existing["id"]),
                    )
                    return int(existing["id"])
                raise sqlite3.IntegrityError("该视频任务已存在")

            cursor = conn.execute(
                """
                INSERT INTO crawl_tasks (
                    bvid, status, interval_seconds, next_run_at,
                    created_at, updated_at
                ) VALUES (?, 'running', ?, ?, ?, ?)
                """,
                (bvid, interval_seconds, now, now, now),
            )
            return int(cursor.lastrowid)

    def get_video(self, bvid: str) -> sqlite3.Row | None:
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM videos WHERE bvid = ?", (bvid,)).fetchone()

    def get_task(self, task_id: int) -> sqlite3.Row | None:
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM crawl_tasks WHERE id = ?", (task_id,)).fetchone()

    def get_task_by_bvid(self, bvid: str) -> sqlite3.Row | None:
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM crawl_tasks WHERE bvid = ?", (bvid,)).fetchone()

    def list_tasks(self, include_stopped: bool = False) -> list[sqlite3.Row]:
        where = "" if include_stopped else "WHERE t.status != 'stopped'"
        with self.database.connect() as conn:
            return conn.execute(
                f"""
                SELECT t.*, v.title, v.owner_name,
                       s.captured_at AS latest_captured_at,
                       s.view_count, s.like_count, s.coin_count, s.favorite_count,
                       s.reply_count, s.danmaku_count, s.share_count, s.online_count, s.online_text
                FROM crawl_tasks t
                JOIN videos v ON v.bvid = t.bvid
                LEFT JOIN video_stats_snapshot s ON s.id = (
                    SELECT id FROM video_stats_snapshot
                    WHERE bvid = t.bvid
                    ORDER BY captured_at DESC, id DESC
                    LIMIT 1
                )
                {where}
                ORDER BY t.created_at DESC
                """
            ).fetchall()

    def count_active_tasks(self) -> int:
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM crawl_tasks WHERE status = 'running'"
            ).fetchone()
            return int(row["n"])

    def set_task_status(self, task_id: int, status: str) -> None:
        now = iso_now()
        with self.database.connect() as conn:
            conn.execute(
                """
                UPDATE crawl_tasks
                SET status=?, updated_at=?, last_error=NULL
                WHERE id=?
                """,
                (status, now, task_id),
            )

    def update_task_schedule(self, bvid: str, next_run_at: datetime) -> None:
        now = iso_now()
        with self.database.connect() as conn:
            conn.execute(
                """
                UPDATE crawl_tasks
                SET next_run_at=?, updated_at=?
                WHERE bvid=?
                """,
                (next_run_at.isoformat(), now, bvid),
            )

    def mark_success(self, bvid: str, interval_seconds: int, jitter_seconds: int = 0) -> None:
        next_run = local_now() + timedelta(seconds=interval_seconds + jitter_seconds)
        now = iso_now()
        with self.database.connect() as conn:
            conn.execute(
                """
                UPDATE crawl_tasks
                SET status='running', last_run_at=?, last_success_at=?,
                    next_run_at=?, consecutive_failures=0,
                    cooldown_until=NULL, last_error=NULL, updated_at=?
                WHERE bvid=?
                """,
                (now, now, next_run.isoformat(), now, bvid),
            )

    def mark_failure(
        self,
        bvid: str,
        message: str,
        cooldown_seconds: int,
        force_error: bool = False,
    ) -> None:
        now_dt = local_now()
        now = now_dt.isoformat()
        with self.database.connect() as conn:
            task = conn.execute(
                "SELECT consecutive_failures FROM crawl_tasks WHERE bvid=?",
                (bvid,),
            ).fetchone()
            failures = int(task["consecutive_failures"] if task else 0) + 1
            status = "error" if force_error or failures >= 3 else "running"
            cooldown_until = (now_dt + timedelta(seconds=cooldown_seconds)).isoformat()
            conn.execute(
                """
                UPDATE crawl_tasks
                SET status=?, last_run_at=?, consecutive_failures=?,
                    cooldown_until=?, next_run_at=?, last_error=?, updated_at=?
                WHERE bvid=?
                """,
                (status, now, failures, cooldown_until, cooldown_until, message, now, bvid),
            )

    def due_running_tasks(self) -> list[sqlite3.Row]:
        now = iso_now()
        with self.database.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM crawl_tasks
                WHERE status='running'
                  AND (cooldown_until IS NULL OR cooldown_until <= ?)
                  AND (next_run_at IS NULL OR next_run_at <= ?)
                ORDER BY next_run_at ASC
                """,
                (now, now),
            ).fetchall()

    def insert_snapshot(
        self,
        stats: VideoStats,
        captured_at: str | None = None,
        source_type: str = "collected",
        source_note: str | None = None,
        collection_source: str = "UNKNOWN",
    ) -> None:
        captured_at = captured_at or iso_now()
        with self.database.connect() as conn:
            conn.execute(
                """
                INSERT INTO video_stats_snapshot (
                    bvid, captured_at, view_count, danmaku_count, reply_count,
                    favorite_count, coin_count, share_count, like_count, online_count, online_text,
                    source_type, source_note, raw_json, collection_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stats.bvid,
                    captured_at,
                    stats.view_count,
                    stats.danmaku_count,
                    stats.reply_count,
                    stats.favorite_count,
                    stats.coin_count,
                    stats.share_count,
                    stats.like_count,
                    stats.online_count,
                    stats.online_text,
                    source_type,
                    source_note,
                    stats.raw_json,
                    collection_source if collection_source in {"MANUAL", "AUTO", "UNKNOWN"} else "UNKNOWN",
                ),
            )

    def insert_history_snapshots(self, bvid: str, rows: list[dict[str, Any]], source_note: str | None = None) -> int:
        if not rows:
            return 0
        with self.database.connect() as conn:
            before = conn.total_changes
            conn.executemany(
                """
                INSERT INTO video_stats_snapshot (
                    bvid, captured_at, view_count, danmaku_count, reply_count,
                    favorite_count, coin_count, share_count, like_count, online_count, online_text,
                    source_type, source_note, raw_json, collection_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported', ?, NULL, 'UNKNOWN')
                """,
                [
                    (
                        bvid,
                        row["captured_at"],
                        row.get("view_count"),
                        row.get("danmaku_count"),
                        row.get("reply_count"),
                        row.get("favorite_count"),
                        row.get("coin_count"),
                        row.get("share_count"),
                        row.get("like_count"),
                        row.get("online_count"),
                        row.get("online_text"),
                        source_note,
                    )
                    for row in rows
                ],
            )
            return int(conn.total_changes - before)

    def list_snapshots(self, bvid: str) -> list[sqlite3.Row]:
        with self.database.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM video_stats_snapshot
                WHERE bvid=?
                ORDER BY captured_at ASC, id ASC
                """,
                (bvid,),
            ).fetchall()

    def latest_snapshot(self, bvid: str) -> sqlite3.Row | None:
        with self.database.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM video_stats_snapshot
                WHERE bvid=?
                ORDER BY captured_at DESC, id DESC
                LIMIT 1
                """,
                (bvid,),
            ).fetchone()

    def delete_snapshots_before(self, bvid: str, before_time: str) -> int:
        with self.database.connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM video_stats_snapshot
                WHERE bvid=? AND captured_at < ?
                """,
                (bvid, before_time),
            )
            return int(cursor.rowcount)

    def add_log(self, level: str, message: str, bvid: str | None = None, detail: str | None = None) -> None:
        with self.database.connect() as conn:
            conn.execute(
                """
                INSERT INTO crawl_logs (bvid, level, message, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (bvid, level, message, detail, iso_now()),
            )

    def list_logs(self, bvid: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
        with self.database.connect() as conn:
            if bvid:
                return conn.execute(
                    """
                    SELECT * FROM crawl_logs
                    WHERE bvid=?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (bvid, limit),
                ).fetchall()
            return conn.execute(
                """
                SELECT * FROM crawl_logs
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def clear_logs(self, bvid: str | None = None) -> int:
        with self.database.connect() as conn:
            if bvid:
                cursor = conn.execute("DELETE FROM crawl_logs WHERE bvid=?", (bvid,))
            else:
                cursor = conn.execute("DELETE FROM crawl_logs")
            return int(cursor.rowcount)

    def clear_raw_json(self, bvid: str | None = None) -> int:
        with self.database.connect() as conn:
            if bvid:
                cur1 = conn.execute("UPDATE videos SET raw_json=NULL WHERE bvid=?", (bvid,))
                cur2 = conn.execute("UPDATE video_stats_snapshot SET raw_json=NULL WHERE bvid=?", (bvid,))
            else:
                cur1 = conn.execute("UPDATE videos SET raw_json=NULL")
                cur2 = conn.execute("UPDATE video_stats_snapshot SET raw_json=NULL")
            return int(cur1.rowcount + cur2.rowcount)

    def insert_comments(self, comments: list[VideoComment], captured_at: str | None = None) -> int:
        if not comments:
            return 0
        captured_at = captured_at or iso_now()
        with self.database.connect() as conn:
            before = conn.total_changes
            conn.executemany(
                """
                INSERT INTO comments (
                    bvid, rpid, parent_rpid, user_mid, user_name, message,
                    like_count, reply_count, ctime, captured_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bvid, rpid) DO UPDATE SET
                    parent_rpid=excluded.parent_rpid,
                    user_mid=excluded.user_mid,
                    user_name=excluded.user_name,
                    message=excluded.message,
                    like_count=excluded.like_count,
                    reply_count=excluded.reply_count,
                    ctime=excluded.ctime,
                    captured_at=excluded.captured_at,
                    raw_json=excluded.raw_json
                """,
                [
                    (
                        item.bvid,
                        item.rpid,
                        item.parent_rpid,
                        item.user_mid,
                        item.user_name,
                        item.message,
                        item.like_count,
                        item.reply_count,
                        item.ctime,
                        captured_at,
                        item.raw_json,
                    )
                    for item in comments
                ],
            )
            return int(conn.total_changes - before)

    def list_comments(self, bvid: str, limit: int = 50) -> list[sqlite3.Row]:
        with self.database.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM comments
                WHERE bvid=?
                ORDER BY captured_at DESC, like_count DESC, id DESC
                LIMIT ?
                """,
                (bvid, limit),
            ).fetchall()

    def insert_danmaku(self, items: list[DanmakuItem], captured_at: str | None = None) -> int:
        if not items:
            return 0
        captured_at = captured_at or iso_now()
        with self.database.connect() as conn:
            before = conn.total_changes
            conn.executemany(
                """
                INSERT INTO danmaku (
                    bvid, cid, progress_sec, text, send_time, captured_at, raw_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.bvid,
                        item.cid,
                        item.progress_sec,
                        item.text,
                        item.send_time,
                        captured_at,
                        item.raw_text,
                    )
                    for item in items
                ],
            )
            return int(conn.total_changes - before)

    def list_danmaku(self, bvid: str, limit: int = 100) -> list[sqlite3.Row]:
        with self.database.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM danmaku
                WHERE bvid=?
                ORDER BY captured_at DESC, progress_sec ASC, id DESC
                LIMIT ?
                """,
                (bvid, limit),
            ).fetchall()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
