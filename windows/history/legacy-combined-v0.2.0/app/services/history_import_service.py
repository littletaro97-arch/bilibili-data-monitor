from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from app.models import AppError


METRIC_FIELDS = {
    "view_count",
    "danmaku_count",
    "reply_count",
    "favorite_count",
    "coin_count",
    "share_count",
    "like_count",
    "online_count",
}
TEXT_FIELDS = {"online_text"}


def parse_history_csv(text: str) -> list[dict[str, int | str | None]]:
    if not text.strip():
        raise AppError("历史记录不能为空")

    reader = csv.DictReader(StringIO(text.strip()))
    if not reader.fieldnames or "captured_at" not in reader.fieldnames:
        raise AppError("历史记录必须包含 captured_at 表头")

    rows: list[dict[str, int | str | None]] = []
    for index, raw in enumerate(reader, start=2):
        captured_at = _normalize_time((raw.get("captured_at") or "").strip(), index)
        parsed: dict[str, int | str | None] = {"captured_at": captured_at}
        has_metric = False
        for field in METRIC_FIELDS:
            value = (raw.get(field) or "").strip()
            parsed[field] = None
            if value == "":
                continue
            try:
                parsed[field] = int(value)
            except ValueError as exc:
                raise AppError(f"第 {index} 行的 {field} 必须是整数") from exc
            has_metric = True
        for field in TEXT_FIELDS:
            value = (raw.get(field) or "").strip()
            parsed[field] = value or None
        if not has_metric:
            raise AppError(f"第 {index} 行至少需要填写一个指标")
        rows.append(parsed)

    if not rows:
        raise AppError("历史记录没有可导入的数据行")
    return rows


def _normalize_time(value: str, row_number: int) -> str:
    if not value:
        raise AppError(f"第 {row_number} 行缺少 captured_at")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AppError(f"第 {row_number} 行 captured_at 时间格式不正确") from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.isoformat()
