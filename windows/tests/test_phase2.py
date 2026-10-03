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
async def test_public_comments_single_page_and_child_limits():
    class Client:
        async def get_json(self, url, params):
            assert url == BilibiliWebProvider.COMMENTS_URL
            assert params == {"type":1, "oid":123456, "pn":1, "ps":20, "sort":2}
            child = {"rpid_str":"9007199254740993", "content":{"message":"<unsafe>"}}
            return {"code":0, "data":{"replies":[{"rpid":100, "content":{"message":"root"}, "replies":[child, child]}]}}
    rows = await BilibiliWebProvider(Client()).fetch_comments("BV1xx411c7mD", 123456, 500, 20)
    assert len(rows) == 2
    assert rows[1].rpid == "9007199254740993"
    assert rows[1].parent_rpid == "100"
    assert rows[1].message == "<unsafe>"


@pytest.mark.asyncio
async def test_manual_collection_cools_down_and_updates_comments(tmp_path):
    repo = make_repo(tmp_path)
    service = Phase2Service(repo, MockVideoDataProvider(), 500, 20)
    await service.collect_comments_once("BV1xx411c7mD")
    with pytest.raises(ProviderError, match="剩余"):
        await service.collect_comments_once("BV1xx411c7mD")
    await service.collect_danmaku_once("BV1xx411c7mD")
    service._last_attempt["评论"] -= 601
    await service.collect_comments_once("BV1xx411c7mD")
    assert len(repo.list_comments("BV1xx411c7mD")) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["<html>blocked</html>", "broken", '<!DOCTYPE i [<!ENTITY x "bad">]><i/>'])
async def test_danmaku_invalid_xml_is_user_visible_error(text):
    class Client:
        async def get_text(self, url): return text
    with pytest.raises(ProviderError):
        await BilibiliWebProvider(Client()).fetch_danmaku("BV1xx411c7mD", 123)


@pytest.mark.asyncio
async def test_failed_comment_request_also_cools_down(tmp_path):
    class FailedProvider(MockVideoDataProvider):
        async def fetch_comments(self, *args, **kwargs):
            raise ProviderError("接口限制")
    service = Phase2Service(make_repo(tmp_path), FailedProvider(), 20, 5)
    with pytest.raises(ProviderError, match="接口限制"):
        await service.collect_comments_once("BV1xx411c7mD")
    with pytest.raises(ProviderError, match="剩余"):
        await service.collect_comments_once("BV1xx411c7mD")


@pytest.mark.asyncio
async def test_empty_and_denied_public_comments():
    class Client:
        payload = {"code":0, "data":{"replies":None}}
        async def get_json(self, *args): return self.payload
    client = Client()
    provider = BilibiliWebProvider(client)
    assert await provider.fetch_comments("BV1xx411c7mD", 123, 20, 5) == []
    client.payload = {"code":-404, "message":"关闭"}
    with pytest.raises(ProviderError):
        await provider.fetch_comments("BV1xx411c7mD", 123, 20, 5)


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
