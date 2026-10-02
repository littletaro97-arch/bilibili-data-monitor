"""Audit v1 exchange checksums using disposable synthetic records, never real user data."""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from app.database import Database, Repository
from app.models import VideoInfo, VideoStats
from app.services.history_exchange_service import HistoryExchangeService, _snapshot_digest


def pack(files: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return output.getvalue()


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="bilibili-integrity-probe-"))
    repo = Repository(Database(root / "synthetic.db"))
    repo.database.initialize()
    repo.upsert_video(VideoInfo("BV1xx411c7mD", title="Synthetic audit sample"))
    repo.insert_snapshot(VideoStats("BV1xx411c7mD", view_count=100), "2026-01-01T00:00:00Z", collection_source="MANUAL")
    service = HistoryExchangeService(repo)
    original = service.export_zip()
    with ZipFile(BytesIO(original)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    snapshots = json.loads(files["snapshots.json"])
    snapshots[0]["viewCount"] = 999999
    files["snapshots.json"] = json.dumps(snapshots).encode()
    corrupt = pack(files)
    try:
        service.preview(corrupt)
        rejected_without_recomputed_hashes = False
    except ValueError:
        rejected_without_recomputed_hashes = True
    snapshots[0]["contentSha256"] = _snapshot_digest(snapshots[0])
    files["snapshots.json"] = json.dumps(snapshots).encode()
    checksums = {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items() if name != "checksums.json"}
    files["checksums.json"] = json.dumps(checksums).encode()
    forged = pack(files)
    accepted = service.preview(forged).snapshots[0]["viewCount"] == 999999
    with repo.database.connect() as conn:
        conn.execute("UPDATE video_stats_snapshot SET view_count=888888")
    sqlite_edit_visible = repo.latest_snapshot("BV1xx411c7mD")["view_count"] == 888888
    (root / "corrupt.zip").write_bytes(corrupt)
    (root / "forged.zip").write_bytes(forged)
    result = {"original_view_count": 100, "forged_view_count": 999999,
              "windows_corruption_rejected": rejected_without_recomputed_hashes,
              "windows_forged_hashes_accepted": accepted, "windows_local_sqlite_edit_visible": sqlite_edit_visible,
              "evidence_directory": str(root)}
    (root / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
