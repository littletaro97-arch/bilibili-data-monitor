from __future__ import annotations

from datetime import datetime
from pathlib import Path

from markupsafe import Markup
from app.config import BASE_DIR

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.database import Repository
from app.services.analysis_service import build_chart_blocks, build_summary


class ReportService:
    def __init__(self, repository: Repository, output_dir: str | Path, template_dir: str | Path):
        self.repository = repository
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
        )

    def generate(self, bvid: str) -> Path:
        video = self.repository.get_video(bvid)
        task = self.repository.get_task_by_bvid(bvid)
        snapshots = self.repository.list_snapshots(bvid)
        latest = snapshots[-1] if snapshots else None
        charts = build_chart_blocks(snapshots, include_plotlyjs=True)
        template = self.env.get_template("report.html.j2")
        generated_at = datetime.now().astimezone().isoformat()
        html = template.render(
            appearance_css=Markup((BASE_DIR / "app/assets/appearance.css").read_text(encoding="utf-8")),
            appearance_js=Markup((BASE_DIR / "app/assets/appearance.js").read_text(encoding="utf-8")),
            video=video,
            task=task,
            snapshots=snapshots,
            latest=latest,
            charts=charts,
            summary=build_summary(snapshots),
            generated_at=generated_at,
            collection_start=snapshots[0]["captured_at"] if snapshots else "暂无",
            collection_end=snapshots[-1]["captured_at"] if snapshots else "暂无",
        )
        path = self.output_dir / f"{bvid}_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S')}.html"
        path.write_text(html, encoding="utf-8")
        self.repository.add_log("INFO", "生成 HTML 报告", bvid=bvid, detail=str(path))
        return path
