from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable

import plotly.graph_objects as go
import plotly.io as pio
from markupsafe import Markup


METRICS = [
    ("view_count", "播放量"),
    ("like_count", "点赞数"),
    ("coin_count", "投币数"),
    ("favorite_count", "收藏数"),
    ("reply_count", "评论数"),
    ("danmaku_count", "弹幕数"),
]


def build_chart_blocks(snapshots: Iterable, include_plotlyjs: bool | str = False) -> list[dict[str, object]]:
    rows = [dict(row) for row in snapshots]
    if len(rows) < 2:
        return [{"title": "趋势图", "html": Markup("<p class=\"empty\">数据不足，继续采集中</p>")}]

    blocks: list[dict[str, object]] = []
    first_chart = True
    for field, title in METRICS:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=[row["captured_at"] for row in rows],
                y=[row.get(field) for row in rows],
                mode="lines+markers",
                name=title,
            )
        )
        fig.update_layout(
            title=title,
            xaxis_title="采集时间",
            yaxis_title="数值",
            margin=dict(l=40, r=20, t=45, b=40),
            height=360,
        )
        blocks.append(
            {
                "title": title,
                "html": Markup(
                    pio.to_html(
                        fig,
                        include_plotlyjs=include_plotlyjs if first_chart else False,
                        full_html=False,
                        default_width="100%",
                        config={"responsive": True, "displaylogo": False},
                    )
                ),
            }
        )
        first_chart = False

    for field, title in [("view_count", "每小时播放增量"), ("like_count", "每小时点赞增量")]:
        hourly = _hourly_increment(rows, field)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(hourly.keys()), y=list(hourly.values()), name=title))
        fig.update_layout(
            title=title,
            xaxis_title="小时",
            yaxis_title="增量",
            margin=dict(l=40, r=20, t=45, b=40),
            height=360,
        )
        blocks.append(
            {
                "title": title,
                "html": Markup(
                    pio.to_html(
                        fig,
                        include_plotlyjs=False,
                        full_html=False,
                        default_width="100%",
                        config={"responsive": True, "displaylogo": False},
                    )
                ),
            }
        )
    return blocks


def build_summary(snapshots: Iterable) -> str:
    rows = [dict(row) for row in snapshots]
    if len(rows) < 2:
        return "当前快照少于 2 条，暂不能计算增长趋势。"
    first = rows[0]
    last = rows[-1]
    view_delta = _delta(first.get("view_count"), last.get("view_count"))
    like_delta = _delta(first.get("like_count"), last.get("like_count"))
    fastest_hour = _fastest_hour(rows, "view_count")
    return (
        f"在本次采集周期内，该视频播放量从 {first.get('view_count')} 增长至 {last.get('view_count')}，"
        f"净增长 {view_delta}。点赞数从 {first.get('like_count')} 增长至 {last.get('like_count')}，"
        f"净增长 {like_delta}。播放量增长最快的小时段为 {fastest_hour}。"
    )


def _delta(start: int | None, end: int | None) -> int | str:
    if start is None or end is None:
        return "未知"
    return int(end) - int(start)


def _hourly_increment(rows: list[dict], field: str) -> dict[str, int]:
    buckets: dict[str, int] = defaultdict(int)
    previous = rows[0]
    for current in rows[1:]:
        previous_value = previous.get(field)
        current_value = current.get(field)
        if previous_value is None or current_value is None:
            previous = current
            continue
        hour = _format_hour(current["captured_at"])
        buckets[hour] += max(0, int(current_value) - int(previous_value))
        previous = current
    return dict(buckets) or {"暂无增量": 0}


def _fastest_hour(rows: list[dict], field: str) -> str:
    hourly = _hourly_increment(rows, field)
    if not hourly or list(hourly.keys()) == ["暂无增量"]:
        return "暂无足够数据"
    return max(hourly.items(), key=lambda item: item[1])[0]


def _format_hour(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:00")
    except ValueError:
        return value[:13]
