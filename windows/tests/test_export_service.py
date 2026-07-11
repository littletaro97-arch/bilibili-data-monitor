from app.database import Database, Repository
from app.models import VideoInfo, VideoStats
from app.services.export_service import ExportService


def test_export_service_writes_csv_files(tmp_path):
    repo = Repository(Database(tmp_path / "test.db"))
    repo.database.initialize()
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7mD", title="Title"))
    repo.insert_snapshot(VideoStats(bvid="BV1xx411c7mD", view_count=1, online_text="10+"))

    path = ExportService(repo, tmp_path / "exports").export_all()

    assert (path / "videos.csv").exists()
    assert (path / "video_stats_snapshot.csv").exists()
    assert (path / "README.txt").exists()
    assert "BV1xx411c7mD" in (path / "videos.csv").read_text(encoding="utf-8-sig")
    assert "10+" in (path / "video_stats_snapshot.csv").read_text(encoding="utf-8-sig")
