from pathlib import Path

from app.database import Database, Repository
from app.models import VideoInfo, VideoStats
from app.services.report_service import ReportService


def make_report_service(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    repo = Repository(db)
    template_dir = Path(__file__).resolve().parents[1] / "reports" / "templates"
    return repo, ReportService(repo, tmp_path / "reports", template_dir)


def test_report_generated_with_insufficient_data(tmp_path):
    repo, service = make_report_service(tmp_path)
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7mD", title="<b>Title</b>", owner_name="UP & Name"))
    repo.create_task("BV1xx411c7mD", 300, min_interval=60, max_active=10)
    path = service.generate("BV1xx411c7mD")
    html = path.read_text(encoding="utf-8")
    assert path.exists()
    assert "BV1xx411c7mD" in html
    assert "&lt;b&gt;Title&lt;/b&gt;" in html
    assert "UP &amp; Name" in html
    assert "数据不足" in html


def test_report_generated_with_charts(tmp_path):
    repo, service = make_report_service(tmp_path)
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7mD", title="Title"))
    repo.create_task("BV1xx411c7mD", 300, min_interval=60, max_active=10)
    repo.insert_snapshot(VideoStats(bvid="BV1xx411c7mD", view_count=1, like_count=1), "2026-01-01T00:00:00+00:00")
    repo.insert_snapshot(VideoStats(bvid="BV1xx411c7mD", view_count=5, like_count=3), "2026-01-01T01:00:00+00:00")
    path = service.generate("BV1xx411c7mD")
    html = path.read_text(encoding="utf-8")
    assert "Plotly.newPlot" in html
    assert "净增长 4" in html
