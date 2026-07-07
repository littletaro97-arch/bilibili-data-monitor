import json

import pytest

from app.collectors.provider import BilibiliWebProvider, MockVideoDataProvider, _as_float, _map_info, _map_stats
from app.models import ProviderError


@pytest.mark.asyncio
async def test_mock_provider_maps_video_info_and_stats():
    provider = MockVideoDataProvider()
    info = await provider.fetch_video_info("BV1xx411c7mD")
    stats = await provider.fetch_video_stats("BV1xx411c7mD")
    assert info.title == "Mock <Video> Title"
    assert info.owner_name == "Mock & UP"
    assert stats.view_count == 12000
    assert stats.like_count == 800
    assert stats.online_count == 42
    assert stats.online_text == "42"


def test_code_not_zero_raises():
    with pytest.raises(ProviderError):
        _map_info("BV1xx411c7mD", {"code": -400, "message": "bad"})


def test_missing_stat_fields_do_not_crash():
    payload = {"code": 0, "data": {"title": "t", "owner": {}, "stat": {}}}
    stats = _map_stats("BV1xx411c7mD", payload)
    assert stats.view_count is None
    assert stats.like_count is None
    assert stats.online_count is None


def test_online_count_can_be_mapped_from_fixed_payload():
    payload = {"code": 0, "data": {"title": "t", "owner": {}, "online": 12, "stat": {"view": 1}}}
    stats = _map_stats("BV1xx411c7mD", payload)
    assert stats.online_count == 12
    assert stats.online_text == "12"


def test_as_float_maps_danmaku_progress():
    assert _as_float("12.5") == 12.5
    assert _as_float("bad") is None
    assert _as_float(None) is None


def test_save_raw_json_is_optional():
    payload = {"code": 0, "data": {"title": "t", "owner": {}, "stat": {"view": 1}}}
    info = _map_info("BV1xx411c7mD", payload, save_raw_json=True)
    assert json.loads(info.raw_json)["code"] == 0


@pytest.mark.asyncio
async def test_web_provider_maps_online_total_endpoint():
    class Client:
        async def get_json(self, url, params=None):
            if "online/total" in url:
                return {"code": 0, "data": {"total": "3000+", "count": "43"}}
            return {
                "code": 0,
                "data": {
                    "aid": 1,
                    "cid": 2,
                    "stat": {"view": 100, "like": 5},
                },
            }

    stats = await BilibiliWebProvider(Client()).fetch_video_stats("BV1xx411c7mD")

    assert stats.online_text == "3000+"
    assert stats.online_count == 3000
