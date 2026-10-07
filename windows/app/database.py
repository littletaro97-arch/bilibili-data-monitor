from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from app.models import AppError, DanmakuItem, RateLimitError, VideoComment, VideoInfo, VideoStats


def local_now() -> datetime:
    return datetime.now().astimezone()


def iso_now() -> str:
    return local_now().isoformat()


def absolute_time_key(value: str) -> datetime:
    """Parse UTC/offset values for ordering; legacy naive values use the current system zone."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


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

                CREATE TABLE IF NOT EXISTS text_collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_text_runs_bvid ON text_collection_runs(bvid, id);
                CREATE TABLE IF NOT EXISTS comment_text_history (
                    bvid TEXT NOT NULL,rpid TEXT NOT NULL,message TEXT NOT NULL,
                    captured_at TEXT NOT NULL, UNIQUE(bvid,rpid,message)
                );
                """
            )
            _ensure_column(conn, "video_stats_snapshot", "source_type", "TEXT NOT NULL DEFAULT 'collected'")
            _ensure_column(conn, "video_stats_snapshot", "source_note", "TEXT")
            _ensure_column(conn, "video_stats_snapshot", "online_count", "INTEGER")
            _ensure_column(conn, "video_stats_snapshot", "online_text", "TEXT")
            _ensure_column(conn, "video_stats_snapshot", "collection_source", "TEXT NOT NULL DEFAULT 'UNKNOWN'")
            _ensure_column(conn, "video_stats_snapshot", "exchange_digest", "TEXT")
            _ensure_column(conn, "danmaku", "source_id", "TEXT")
            for table in ("comments", "danmaku"):
                _ensure_column(conn, table, "visibility", "TEXT NOT NULL DEFAULT 'unknown'")
                _ensure_column(conn, table, "visibility_checked_at", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_danmaku_identity ON danmaku(bvid,cid,progress_sec,send_time)")
            from app.up_monitor_store import SCHEMA
            conn.executescript(SCHEMA)
            _ensure_column(conn, "crawl_tasks", "failure_kind", "TEXT")
            _ensure_column(conn, "crawl_tasks", "automatic", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(conn, "up_monitors", "scan_page", "INTEGER NOT NULL DEFAULT 1")
            _ensure_column(conn, "up_monitors", "scan_max_pubdate", "INTEGER")
            conn.execute("""UPDATE crawl_tasks SET automatic=1 WHERE automatic=0 AND (
                EXISTS (SELECT 1 FROM up_monitor_videos u WHERE u.bvid=crawl_tasks.bvid AND u.state='queued' AND u.promoted=0)
                OR EXISTS (SELECT 1 FROM video_stats_snapshot s WHERE s.bvid=crawl_tasks.bvid AND s.source_type='collected' AND s.collection_source='UP_MONITOR'))""")
            _ensure_column(conn, "up_monitors", "failure_kind", "TEXT")
            _ensure_column(conn, "html_reports", "deleted", "INTEGER NOT NULL DEFAULT 0")
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

    def create_task(self, bvid: str, interval_seconds: int, min_interval: int, max_active: int | None, *, automatic: bool = False) -> int:
        if interval_seconds < min_interval:
            raise RateLimitError(f"采集间隔不得低于 {min_interval} 秒")
        if max_active is not None and self.count_active_tasks(manual_only=True) >= max_active:
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
                    created_at, updated_at, automatic
                ) VALUES (?, 'running', ?, ?, ?, ?, ?)
                """,
                (bvid, interval_seconds, now, now, now, int(automatic)),
            )
            return int(cursor.lastrowid)

    def get_video(self, bvid: str) -> sqlite3.Row | None:
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM videos WHERE bvid = ?", (bvid,)).fetchone()

    def update_video_cover(self, bvid: str, cover_url: str) -> None:
        with self.database.connect() as conn:
            conn.execute("UPDATE videos SET cover_url=?, updated_at=? WHERE bvid=?", (cover_url, iso_now(), bvid))

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

    def count_active_tasks(self, manual_only: bool = False) -> int:
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM crawl_tasks WHERE status = 'running'" + (" AND automatic=0" if manual_only else "")
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

    def set_task_interval(self, task_id: int, seconds: int, minimum: int) -> None:
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not minimum <= seconds <= 31536000:
            raise RateLimitError(f"采集间隔须为 {minimum} 至 31536000 秒的整数")
        now = local_now()
        with self.database.connect() as conn:
            task = conn.execute('SELECT * FROM crawl_tasks WHERE id=?', (task_id,)).fetchone()
            if not task or task['status']=='stopped':
                raise RateLimitError('任务不存在或已在回收站中')
            # Leave status, failure count and platform cooldown intact.
            conn.execute('UPDATE crawl_tasks SET interval_seconds=?,next_run_at=?,updated_at=? WHERE id=?',
                         (seconds,(now+timedelta(seconds=seconds)).isoformat(),now.isoformat(),task_id))

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
            current = conn.execute('SELECT interval_seconds FROM crawl_tasks WHERE bvid=?', (bvid,)).fetchone()
            if current:
                next_run = local_now() + timedelta(seconds=current['interval_seconds'] + jitter_seconds)
            conn.execute(
                """
                UPDATE crawl_tasks
                SET status=CASE WHEN status IN ('paused', 'stopped') THEN status ELSE 'running' END, last_run_at=?, last_success_at=?,
                    next_run_at=?, consecutive_failures=0,
                    cooldown_until=NULL, last_error=NULL, failure_kind=NULL, updated_at=?
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
        failure_kind: str | None = None,
    ) -> None:
        now_dt = local_now()
        now = now_dt.isoformat()
        with self.database.connect() as conn:
            task = conn.execute(
                "SELECT consecutive_failures FROM crawl_tasks WHERE bvid=?",
                (bvid,),
            ).fetchone()
            failures = int(task["consecutive_failures"] if task else 0) + 1
            failure_kind = "risk" if force_error else (failure_kind or "provider")
            status = "error" if force_error or (failures >= 3 and failure_kind not in {"network","timeout"}) else "running"
            cooldown_until = (now_dt + timedelta(seconds=cooldown_seconds)).isoformat()
            conn.execute(
                """
                UPDATE crawl_tasks
                SET status=CASE WHEN status IN ('paused', 'stopped') THEN status ELSE ? END, last_run_at=?, consecutive_failures=?,
                    cooldown_until=?, next_run_at=?, last_error=?, updated_at=?, failure_kind=?
                WHERE bvid=?
                """,
                (status, now, failures, cooldown_until, cooldown_until, message, now, failure_kind, bvid),
            )

    def due_running_tasks(self, limit: int | None = None) -> list[sqlite3.Row]:
        now = iso_now()
        with self.database.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM crawl_tasks
                WHERE status='running'
                  AND (cooldown_until IS NULL OR cooldown_until <= ?)
                  AND (next_run_at IS NULL OR next_run_at <= ?)
                ORDER BY next_run_at ASC
                LIMIT ?
                """,
                (now, now, limit if limit is not None else -1),
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
            rows = conn.execute(
                """
                SELECT * FROM video_stats_snapshot
                WHERE bvid=?
                ORDER BY captured_at ASC, id ASC
                """,
                (bvid,),
            ).fetchall()
        return sorted(rows, key=lambda row: (absolute_time_key(row["captured_at"]), row["id"]))

    def latest_snapshot(self, bvid: str) -> sqlite3.Row | None:
        rows = self.list_snapshots(bvid)
        return rows[-1] if rows else None

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
            # Preserve previously observed text before any platform edit or tombstone.
            for item in comments:
                conn.execute('''INSERT OR IGNORE INTO comment_text_history(bvid,rpid,message,captured_at)
                    SELECT bvid,rpid,message,captured_at FROM comments
                    WHERE bvid=? AND rpid=? AND message IS NOT NULL AND message<>'' AND message IS NOT ?''',
                    (item.bvid,item.rpid,item.message))
            before = conn.total_changes
            conn.executemany(
                """
                INSERT INTO comments (
                    bvid, rpid, parent_rpid, user_mid, user_name, message,
                    like_count, reply_count, ctime, captured_at, raw_json, visibility, visibility_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bvid, rpid) DO UPDATE SET
                    parent_rpid=excluded.parent_rpid,
                    user_mid=excluded.user_mid,
                    user_name=CASE WHEN excluded.user_name IS NULL OR excluded.user_name='' THEN comments.user_name ELSE excluded.user_name END,
                    message=CASE WHEN excluded.message IS NULL OR excluded.message IN ('','[已删除]','该评论已被删除','该评论已被删除。','评论已删除') THEN comments.message ELSE excluded.message END,
                    like_count=excluded.like_count,
                    reply_count=excluded.reply_count,
                    ctime=CASE WHEN excluded.ctime IS NULL OR excluded.ctime=0 THEN comments.ctime ELSE excluded.ctime END,
                    captured_at=excluded.captured_at,
                    raw_json=excluded.raw_json,
                    visibility=CASE WHEN excluded.visibility='unknown' THEN comments.visibility ELSE excluded.visibility END,
                    visibility_checked_at=CASE WHEN excluded.visibility='unknown' THEN comments.visibility_checked_at ELSE excluded.visibility_checked_at END
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
                        ('unknown' if item.rpid.startswith('local-comment-') or not item.message else 'placeholder' if item.message in ('[已删除]','该评论已被删除','该评论已被删除。','评论已删除') else 'observed'),
                        captured_at,
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

    def text_dashboard_data(self, bvid: str, limit: int = 10000):
        """Bound the browser payload, not analysis to the old first 200/500 rows."""
        import json
        with self.database.connect() as conn:
            comments = conn.execute("SELECT * FROM comments WHERE bvid=? ORDER BY captured_at DESC,id DESC LIMIT ?", (bvid, limit)).fetchall()
            # Repeated XML fetches must not inflate density or word frequencies.
            groups = "cid,source_id,progress_sec,send_time,text,CASE WHEN raw_text IS NULL THEN 'public' ELSE 'local' END"
            # Match legacy rows to newer identified records without rewriting user data.
            where = """FROM danmaku d WHERE bvid=? AND (source_id IS NOT NULL OR raw_text IS NOT NULL OR NOT EXISTS (
                SELECT 1 FROM danmaku n WHERE n.source_id IS NOT NULL AND n.bvid=d.bvid AND n.cid IS d.cid
                AND n.progress_sec IS d.progress_sec AND n.send_time IS d.send_time AND n.text IS d.text))"""
            dm = conn.execute(f"SELECT cid,progress_sec,send_time,text,MAX(captured_at) AS captured_at,CASE WHEN MAX(CASE WHEN visibility='observed' THEN 1 ELSE 0 END)=1 THEN 'observed' ELSE 'unknown' END AS visibility,MAX(visibility_checked_at) AS visibility_checked_at,CASE WHEN raw_text IS NULL THEN 'public' ELSE 'local' END AS origin {where} GROUP BY {groups} ORDER BY captured_at DESC LIMIT ?", (bvid, limit)).fetchall()
            comment_count = conn.execute("SELECT COUNT(*) FROM comments WHERE bvid=?", (bvid,)).fetchone()[0]
            dm_count = conn.execute(f"SELECT COUNT(*) FROM (SELECT 1 {where} GROUP BY {groups})", (bvid,)).fetchone()[0]
            raw_count = conn.execute("SELECT COUNT(*) FROM danmaku WHERE bvid=?", (bvid,)).fetchone()[0]
            runs = conn.execute("SELECT kind,captured_at,metadata_json FROM text_collection_runs WHERE bvid=? ORDER BY id DESC LIMIT 10", (bvid,)).fetchall()
        return {"comments": [dict(row) for row in comments], "danmaku": [dict(row) for row in dm],
            "stored_comments": comment_count, "stored_danmaku": dm_count, "raw_danmaku": raw_count,
            "limit": limit, "truncated": comment_count > limit or dm_count > limit,
            "runs": [{"kind": row["kind"], "captured_at": row["captured_at"], "metadata": json.loads(row["metadata_json"])} for row in runs]}

    def record_text_collection(self, bvid: str, kind: str, metadata):
        import json
        with self.database.connect() as conn:
            conn.execute("INSERT INTO text_collection_runs(bvid,kind,captured_at,metadata_json) VALUES(?,?,?,?)",
                (bvid, kind, iso_now(), json.dumps(metadata, ensure_ascii=False)))

    def insert_danmaku(self, items: list[DanmakuItem], captured_at: str | None = None) -> int:
        if not items:
            return 0
        captured_at = captured_at or iso_now()
        with self.database.connect() as conn:
            before = conn.total_changes
            conn.executemany(
                """
                INSERT INTO danmaku (
                    bvid, cid, progress_sec, text, send_time, captured_at, raw_text, source_id, visibility, visibility_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        item.source_id,
                        'observed' if item.raw_text is None else 'unknown',
                        captured_at if item.raw_text is None else None,
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

    def count_monitored_videos(self):
        with self.database.connect() as c:return c.execute("SELECT COUNT(*) FROM crawl_tasks WHERE status!='stopped'").fetchone()[0]

    def permanently_delete_task(self,task_id):
        with self.database.connect() as c:
            task=c.execute('SELECT * FROM crawl_tasks WHERE id=?',(task_id,)).fetchone()
            if not task or task['status']!='stopped':raise AppError('只有回收站中的任务可以永久删除')
            bvid=task['bvid']
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='text_jobs'").fetchone():
                for table in ('text_job_roots','text_job_cursors'):
                    c.execute(f'DELETE FROM {table} WHERE job IN (SELECT id FROM text_jobs WHERE bvid=?)',(bvid,))
                c.execute('DELETE FROM text_jobs WHERE bvid=?',(bvid,))
            for table in ('video_stats_snapshot','comments','danmaku','comment_text_history','text_collection_runs','crawl_logs','crawl_tasks'):
                c.execute(f'DELETE FROM {table} WHERE bvid=?',(bvid,))
            c.execute("UPDATE up_monitor_videos SET state='deleted',title='',promoted=1 WHERE bvid=?",(bvid,))
            c.execute('DELETE FROM videos WHERE bvid=?',(bvid,))
            return bvid


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
