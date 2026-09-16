import asyncio

import pytest

from app.collectors.bilibili_client import BilibiliClient
from app.database import Database, Repository
from app.models import RateLimitError, VideoInfo


def test_reject_interval_below_minimum(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    repo = Repository(db)
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7mD"))
    with pytest.raises(RateLimitError):
        repo.create_task("BV1xx411c7mD", 10, min_interval=60, max_active=10)


def test_reject_more_than_max_running_tasks(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    repo = Repository(db)
    for idx in range(10):
        bvid = f"BV1xx411c7{idx:02d}"
        repo.upsert_video(VideoInfo(bvid=bvid))
        repo.create_task(bvid, 300, min_interval=60, max_active=10)
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7ZZ"))
    with pytest.raises(RateLimitError):
        repo.create_task("BV1xx411c7ZZ", 300, min_interval=60, max_active=10)


def test_risk_payload_does_not_retry():
    client = BilibiliClient(min_interval_seconds=0, max_retries=2)
    with pytest.raises(Exception):
        client._detect_risk_payload({"code": 412, "message": "风控"})


def test_min_request_interval_is_configured():
    client = BilibiliClient(min_interval_seconds=3)
    assert client.min_interval_seconds == 3
