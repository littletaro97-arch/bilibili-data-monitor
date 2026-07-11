from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import sqlite3

from app.database import Repository


EXPORT_TABLES = {
    "videos": "SELECT * FROM videos ORDER BY created_at ASC, id ASC",
    "crawl_tasks": "SELECT * FROM crawl_tasks ORDER BY created_at ASC, id ASC",
    "video_stats_snapshot": "SELECT * FROM video_stats_snapshot ORDER BY bvid ASC, captured_at ASC, id ASC",
    "comments": "SELECT * FROM comments ORDER BY bvid ASC, captured_at ASC, id ASC",
    "danmaku": "SELECT * FROM danmaku ORDER BY bvid ASC, captured_at ASC, id ASC",
    "crawl_logs": "SELECT * FROM crawl_logs ORDER BY created_at ASC, id ASC",
}


class ExportService:
    def __init__(self, repository: Repository, output_dir: str | Path):
        self.repository = repository
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self) -> Path:
        target = self.output_dir / datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        target.mkdir(parents=True, exist_ok=False)
        with self.repository.database.connect() as conn:
            for name, query in EXPORT_TABLES.items():
                rows = conn.execute(query).fetchall()
                _write_csv(target / f"{name}.csv", rows)
        (target / "README.txt").write_text(
            "本目录由程序导出，CSV 使用 UTF-8 with BOM 编码，可直接用 Excel 打开。\n"
            "video_stats_snapshot.source_type=collected 表示程序自动采集，imported 表示手动导入历史记录。\n",
            encoding="utf-8-sig",
        )
        self.repository.add_log("INFO", "导出全部数据", detail=str(target))
        return target


def _write_csv(path: Path, rows: list[sqlite3.Row]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        if not rows:
            handle.write("")
            return
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
