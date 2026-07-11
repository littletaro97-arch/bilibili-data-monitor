import pytest

from app.collectors.bilibili_client import BilibiliClient
from app.collectors.provider import BilibiliWebProvider, MockVideoDataProvider
from app.database import Database, Repository
from app.models import ProviderError, VideoInfo
from app.services.phase2_service import Phase2Service


def make_repo(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    repo = Repository(db)
    repo.upsert_video(VideoInfo(bvid="BV1xx411c7mD", aid=123456, cid=654321, title="Title"))
    return repo


@pytest.mark.asyncio
async def test_phase2_mock_comments_and_danmaku_are_saved(tmp_path):
    repo = make_repo(tmp_path)
    service = Phase2Service(repo, MockVideoDataProvider(), max_root_comments=500, max_child_comments=20)

    comment_count = await service.collect_comments_once("BV1xx411c7mD")
    danmaku_count = await service.collect_danmaku_once("BV1xx411c7mD")

    assert comment_count == 1
    assert danmaku_count == 1
    assert repo.list_comments("BV1xx411c7mD")[0]["message"] == "Mock comment <unsafe>"
    assert repo.list_danmaku("BV1xx411c7mD")[0]["text"] == "Mock danmaku <unsafe>"


@pytest.mark.asyncio
async def test_real_comment_provider_requires_documented_source():
    provider = BilibiliWebProvider(BilibiliClient(min_interval_seconds=0))
    with pytest.raises(ProviderError):
        await provider.fetch_comments("BV1xx411c7mD", aid=123456, max_root=500, max_child=20)


def test_import_comments_and_danmaku_text(tmp_path):
    repo = make_repo(tmp_path)
    service = Phase2Service(repo, MockVideoDataProvider(), max_root_comments=500, max_child_comments=20)

    comment_count = service.import_comments_text("BV1xx411c7mD", "讲解清楚\n数据分析有用")
    danmaku_count = service.import_danmaku_text("BV1xx411c7mD", "12.5,这里弹幕密集\n普通弹幕")

    comments = repo.list_comments("BV1xx411c7mD")
    danmaku = repo.list_danmaku("BV1xx411c7mD")

    assert comment_count == 2
    assert danmaku_count == 2
    assert comments[0]["message"] in {"讲解清楚", "数据分析有用"}
    assert danmaku[0]["progress_sec"] in {5.0, 12.5}


def test_seed_demo_data(tmp_path):
    repo = make_repo(tmp_path)
    service = Phase2Service(repo, MockVideoDataProvider(), max_root_comments=500, max_child_comments=20)

    comment_count, danmaku_count = service.seed_demo_data("BV1xx411c7mD")

    assert comment_count > 0
    assert danmaku_count > 0
    assert repo.list_comments("BV1xx411c7mD")
    assert repo.list_danmaku("BV1xx411c7mD")
