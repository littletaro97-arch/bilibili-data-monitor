import pytest

from app.collectors.video_info import parse_bvid
from app.models import InvalidBvidError


def test_parse_plain_bvid():
    assert parse_bvid("BV1xx411c7mD") == "BV1xx411c7mD"


def test_parse_video_url():
    assert parse_bvid("https://www.bilibili.com/video/BV1xx411c7mD/") == "BV1xx411c7mD"


def test_parse_video_url_with_query():
    url = "https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.1007"
    assert parse_bvid(url) == "BV1xx411c7mD"


@pytest.mark.parametrize("value", ["", "hello", "BV123"])
def test_parse_invalid(value):
    with pytest.raises(InvalidBvidError):
        parse_bvid(value)
