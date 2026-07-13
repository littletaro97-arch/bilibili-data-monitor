from __future__ import annotations

from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.database import Database, Repository
from app.services.history_exchange_service import ExchangePreview, HistoryExchangeService, _snapshot_digest, _utc_time


def _repository(path) -> Repository:
    database = Database(path)
    database.initialize()
    repository = Repository(database)
    with database.connect() as conn:
        now = "2026-01-01T00:00:00+00:00"
        conn.execute(
            "INSERT INTO videos (bvid,title,cover_url,created_at,updated_at) VALUES (?,?,?,?,?)",
            ("BV1xx411c7mD", "中文标题😀", "https://i0.hdslb.com/bfs/archive/cover.jpg", now, now),
        )
        conn.execute(
            """INSERT INTO video_stats_snapshot
               (bvid,captured_at,view_count,like_count,source_type,collection_source)
               VALUES (?,?,?,?,?,?)""",
            ("BV1xx411c7mD", now, 100, 5, "collected", "MANUAL"),
        )
    return repository


def test_cross_database_round_trip_and_duplicate(tmp_path):
    source = _repository(tmp_path / "source.db")
    payload = HistoryExchangeService(source).export_zip()
    target_db = Database(tmp_path / "target.db")
    target_db.initialize()
    target = HistoryExchangeService(Repository(target_db))
    preview = target.preview(payload)
    first = target.merge(preview)
    second = target.merge(preview)
    assert (first.videos_added, first.snapshots_added, first.conflicts) == (1, 1, 0)
    assert (second.videos_added, second.snapshots_added, second.duplicates) == (0, 0, 1)
    with target_db.connect() as conn:
        assert conn.execute("SELECT cover_url FROM videos WHERE bvid=?", ("BV1xx411c7mD",)).fetchone()[0] == "https://i0.hdslb.com/bfs/archive/cover.jpg"


def test_checksum_corruption_is_rejected(tmp_path):
    payload = HistoryExchangeService(_repository(tmp_path / "source.db")).export_zip()
    files = {}
    with ZipFile(BytesIO(payload)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    files["snapshots.json"] += b" "
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    with pytest.raises(ValueError, match="SHA-256"):
        HistoryExchangeService(_repository(tmp_path / "other.db")).preview(output.getvalue())


def test_future_version_is_rejected(tmp_path):
    service = HistoryExchangeService(_repository(tmp_path / "source.db"))
    payload = service.export_zip()
    with ZipFile(BytesIO(payload)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files["manifest.json"])
    manifest["formatVersion"] = 2
    files["manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    checksums = json.loads(files["checksums.json"])
    from hashlib import sha256
    checksums["manifest.json"] = sha256(files["manifest.json"]).hexdigest()
    files["checksums.json"] = json.dumps(checksums, sort_keys=True, separators=(",", ":")).encode()
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items(): archive.writestr(name, content)
    with pytest.raises(ValueError, match="formatVersion"):
        service.preview(output.getvalue())


def test_database_migration_sets_version_and_preserves_rows(tmp_path):
    path = tmp_path / "legacy.db"
    database = Database(path)
    database.initialize()
    with database.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        columns = {row[1] for row in conn.execute("PRAGMA table_info(video_stats_snapshot)")}
    assert {"collection_source", "exchange_digest"} <= columns


def test_utc_format_matches_java_instant_groups():
    assert _utc_time("2026-01-01T00:00:00.123000+00:00") == "2026-01-01T00:00:00.123Z"
    assert _utc_time("2026-01-01T00:00:00.683730+00:00") == "2026-01-01T00:00:00.683730Z"


def test_same_identity_different_content_is_conflict(tmp_path):
    source = _repository(tmp_path / "source.db")
    service = HistoryExchangeService(source)
    preview = service.preview(service.export_zip())
    changed = dict(preview.snapshots[0])
    changed["viewCount"] += 1
    changed["contentSha256"] = _snapshot_digest(changed)
    report = service.merge(ExchangePreview(preview.manifest, preview.videos, [changed]))
    assert report.conflicts == 1
    assert report.snapshots_added == 0


def test_zip_slip_entry_is_rejected(tmp_path):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("../manifest.json", b"{}")
        archive.writestr("videos.json", b"[]")
        archive.writestr("snapshots.json", b"[]")
        archive.writestr("checksums.json", b"{}")
    service = HistoryExchangeService(_repository(tmp_path / "source.db"))
    with pytest.raises(ValueError, match="结构|非法"):
        service.preview(output.getvalue())


def test_export_orders_snapshots_by_canonical_utc_time(tmp_path):
    repository = _repository(tmp_path / "source.db")
    with repository.database.connect() as conn:
        conn.execute(
            "INSERT INTO video_stats_snapshot (bvid,captured_at,view_count,source_type,collection_source) VALUES (?,?,?,?,?)",
            ("BV1xx411c7mD", "2025-12-31T19:30:00-05:00", 90, "collected", "AUTO"),
        )
    service = HistoryExchangeService(repository)
    preview = service.preview(service.export_zip())

    assert [item["viewCount"] for item in preview.snapshots] == [100, 90]
    assert preview.snapshots[0]["collectedAt"] == "2026-01-01T00:00:00Z"
    assert preview.snapshots[1]["collectedAt"] == "2026-01-01T00:30:00Z"
