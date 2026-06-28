from datetime import datetime, timedelta

from app.database import Database, Repository
from app.models import DanmakuItem, VideoComment, VideoInfo, VideoStats


def make_repo(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return Repository(db)


def test_database_initialize_and_video_task_flow(tmp_path):
    repo = make_repo(tmp_path)
    info = VideoInfo(bvid="BV1xx411c7mD", title="Title", owner_name="UP")
    repo.upsert_video(info)
    repo.upsert_video(info)
    assert repo.get_video("BV1xx411c7mD")["title"] == "Title"

    task_id = repo.create_task("BV1xx411c7mD", 300, min_interval=60, max_active=10)
    assert repo.get_task(task_id)["status"] == "running"

    repo.set_task_status(task_id, "paused")
    assert repo.get_task(task_id)["status"] == "paused"
    repo.set_task_status(task_id, "running")
    assert repo.get_task(task_id)["status"] == "running"
    repo.set_task_status(task_id, "stopped")
    assert repo.get_task(task_id)["status"] == "stopped"


def test_failure_cooldown_and_snapshots(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7mD"))
    repo.create_task("BV1xx411c7mD", 300, min_interval=60, max_active=10)

    repo.mark_failure("BV1xx411c7mD", "timeout", cooldown_seconds=600)
    task = repo.get_task_by_bvid("BV1xx411c7mD")
    assert task["consecutive_failures"] == 1
    assert datetime.fromisoformat(task["cooldown_until"]) > datetime.now().astimezone() + timedelta(seconds=500)

    repo.insert_snapshot(VideoStats(bvid="BV1xx411c7mD", view_count=1, like_count=2))
    rows = repo.list_snapshots("BV1xx411c7mD")
    assert len(rows) == 1
    assert rows[0]["view_count"] == 1


def test_phase2_tables_insert_and_query(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7mD"))
    repo.insert_comments(
        [
            VideoComment(
                bvid="BV1xx411c7mD",
                rpid="1",
                user_name="u",
                message="<script>",
                like_count=1,
            )
        ]
    )
    repo.insert_danmaku(
        [
            DanmakuItem(
                bvid="BV1xx411c7mD",
                cid=1,
                progress_sec=2.5,
                text="<b>danmaku</b>",
            )
        ]
    )
    assert repo.list_comments("BV1xx411c7mD")[0]["message"] == "<script>"
    assert repo.list_danmaku("BV1xx411c7mD")[0]["text"] == "<b>danmaku</b>"


def test_clear_logs(tmp_path):
    repo = make_repo(tmp_path)
    repo.add_log("INFO", "one", bvid="BV1xx411c7mD")
    repo.add_log("ERROR", "two")
    assert len(repo.list_logs(limit=10)) == 2
    assert repo.clear_logs(bvid="BV1xx411c7mD") == 1
    assert len(repo.list_logs(limit=10)) == 1
    assert repo.clear_logs() == 1
    assert repo.list_logs(limit=10) == []


def test_delete_snapshots_before(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7mD"))
    repo.insert_snapshot(VideoStats(bvid="BV1xx411c7mD", view_count=1), "2026-01-01T10:00:00+08:00")
    repo.insert_snapshot(VideoStats(bvid="BV1xx411c7mD", view_count=2), "2026-01-02T10:00:00+08:00")

    deleted = repo.delete_snapshots_before("BV1xx411c7mD", "2026-01-02T00:00:00+08:00")
    rows = repo.list_snapshots("BV1xx411c7mD")

    assert deleted == 1
    assert len(rows) == 1
    assert rows[0]["view_count"] == 2
