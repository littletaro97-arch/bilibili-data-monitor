import json

import pytest

from app.collectors.provider import MockVideoDataProvider, _map_info, _map_stats
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


def test_code_not_zero_raises():
    with pytest.raises(ProviderError):
        _map_info("BV1xx411c7mD", {"code": -400, "message": "bad"})


def test_missing_stat_fields_do_not_crash():
    payload = {"code": 0, "data": {"title": "t", "owner": {}, "stat": {}}}
    stats = _map_stats("BV1xx411c7mD", payload)
    assert stats.view_count is None
    assert stats.like_count is None


def test_save_raw_json_is_optional():
    payload = {"code": 0, "data": {"title": "t", "owner": {}, "stat": {"view": 1}}}
    info = _map_info("BV1xx411c7mD", payload, save_raw_json=True)
    assert json.loads(info.raw_json)["code"] == 0
