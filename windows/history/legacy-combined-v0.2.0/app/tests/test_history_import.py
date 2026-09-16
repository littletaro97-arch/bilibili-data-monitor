import pytest

from app.models import AppError
from app.services.history_import_service import parse_history_csv


def test_parse_history_csv_accepts_metric_columns():
    rows = parse_history_csv(
        "captured_at,view_count,like_count\n"
        "2026-06-01T10:00:00+08:00,100,5\n"
    )

    assert rows == [
        {
            "captured_at": "2026-06-01T10:00:00+08:00",
            "coin_count": None,
            "danmaku_count": None,
            "favorite_count": None,
            "like_count": 5,
            "online_count": None,
            "online_text": None,
            "reply_count": None,
            "share_count": None,
            "view_count": 100,
        }
    ]


def test_parse_history_csv_requires_captured_at():
    with pytest.raises(AppError):
        parse_history_csv("view_count\n100\n")


def test_parse_history_csv_rejects_non_integer_metric():
    with pytest.raises(AppError):
        parse_history_csv("captured_at,view_count\n2026-06-01T10:00:00+08:00,abc\n")
