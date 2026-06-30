from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import re
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
    ("online_count", "当前观看人数"),
]

METRIC_LABELS = dict(METRICS)

STOPWORDS = {
    "的",
    "了",
    "是",
    "我",
    "你",
    "他",
    "她",
    "它",
    "啊",
    "吗",
    "呢",
    "吧",
    "和",
    "也",
    "就",
    "都",
    "很",
    "在",
    "有",
    "这",
    "那",
    "一个",
    "这个",
    "不是",
    "没有",
    "哈哈",
    "哈哈哈",
    "the",
    "and",
    "for",
    "you",
    "that",
    "this",
}


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
            margin=dict(l=40, r=20, t=45, b=_bottom_margin(rows)),
            height=360,
        )
        _add_source_note(fig, rows)
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


def build_dual_axis_chart(
    snapshots: Iterable,
    left_field: str = "view_count",
    right_field: str = "like_count",
    include_plotlyjs: bool | str = False,
) -> Markup:
    rows = [dict(row) for row in snapshots]
    if len(rows) < 2:
        return Markup("<p class=\"empty\">数据不足，至少需要 2 条快照才能生成对比图</p>")

    if left_field not in METRIC_LABELS:
        left_field = "view_count"
    if right_field not in METRIC_LABELS:
        right_field = "like_count"

    left_label = METRIC_LABELS[left_field]
    right_label = METRIC_LABELS[right_field]
    x_values = [row["captured_at"] for row in rows]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=[row.get(left_field) for row in rows],
            mode="lines+markers",
            name=left_label,
            yaxis="y",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=[row.get(right_field) for row in rows],
            mode="lines+markers",
            name=right_label,
            yaxis="y2",
        )
    )
    fig.update_layout(
        title=f"{left_label} / {right_label} 对比",
        xaxis_title="采集时间",
        yaxis=dict(title=left_label),
        yaxis2=dict(title=right_label, overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=48, r=56, t=58, b=_bottom_margin(rows)),
        height=380,
    )
    _add_source_note(fig, rows)
    return Markup(
        pio.to_html(
            fig,
            include_plotlyjs=include_plotlyjs,
            full_html=False,
            default_width="100%",
            config={"responsive": True, "displaylogo": False},
        )
    )


def build_ratio_chart(
    snapshots: Iterable,
    numerator_field: str = "like_count",
    denominator_field: str = "view_count",
    include_plotlyjs: bool | str = False,
) -> Markup:
    rows = [dict(row) for row in snapshots]
    if len(rows) < 2:
        return Markup("<p class=\"empty\">数据不足，至少需要 2 条快照才能生成比值图</p>")

    if numerator_field not in METRIC_LABELS:
        numerator_field = "like_count"
    if denominator_field not in METRIC_LABELS:
        denominator_field = "view_count"

    numerator_label = METRIC_LABELS[numerator_field]
    denominator_label = METRIC_LABELS[denominator_field]
    x_values = [row["captured_at"] for row in rows]
    ratios = [_safe_ratio(row.get(numerator_field), row.get(denominator_field)) for row in rows]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=[row.get(numerator_field) for row in rows],
            mode="lines+markers",
            name=numerator_label,
            yaxis="y",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=[row.get(denominator_field) for row in rows],
            mode="lines+markers",
            name=denominator_label,
            yaxis="y",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=ratios,
            mode="lines+markers",
            name=f"{numerator_label}/{denominator_label}",
            yaxis="y2",
        )
    )
    fig.update_layout(
        title=f"{numerator_label} / {denominator_label} 比值",
        xaxis_title="采集时间",
        yaxis=dict(title="实际数量"),
        yaxis2=dict(title="比值", overlaying="y", side="right", tickformat=".2%"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=48, r=64, t=58, b=_bottom_margin(rows)),
        height=390,
    )
    _add_source_note(fig, rows)
    return Markup(
        pio.to_html(
            fig,
            include_plotlyjs=include_plotlyjs,
            full_html=False,
            default_width="100%",
            config={"responsive": True, "displaylogo": False},
        )
    )


def build_summary(snapshots: Iterable) -> str | Markup:
    rows = [dict(row) for row in snapshots]
    if len(rows) < 2:
        return "当前快照少于 2 条，暂不能计算增长趋势。"
    first = rows[0]
    last = rows[-1]
    view_delta = _delta(first.get("view_count"), last.get("view_count"))
    like_delta = _delta(first.get("like_count"), last.get("like_count"))
    fastest_hour = _fastest_hour(rows, "view_count")
    return Markup(
        "在本次采集周期内，该视频播放量从 "
        f"{_highlight(first.get('view_count'))} 增长至 {_highlight(last.get('view_count'))}，"
        f"{_highlight(f'净增长 {view_delta}')}。点赞数从 {_highlight(first.get('like_count'))} "
        f"增长至 {_highlight(last.get('like_count'))}，{_highlight(f'净增长 {like_delta}')}。"
        f"播放量增长最快的小时段为 {_highlight(fastest_hour)}。"
    )


def top_words(rows: Iterable, field: str = "message", limit: int = 20) -> list[dict[str, int | str]]:
    counter: Counter[str] = Counter()
    for row in rows:
        text = (dict(row).get(field) or "").strip()
        counter.update(_tokenize(text))
    return [{"word": word, "count": count} for word, count in counter.most_common(limit)]


def build_danmaku_density_chart(danmaku_rows: Iterable, bucket_seconds: int = 30) -> Markup:
    rows = [dict(row) for row in danmaku_rows]
    points = [row.get("progress_sec") for row in rows if row.get("progress_sec") is not None]
    if not points:
        return Markup("<p class=\"empty\">暂无足够弹幕时间数据</p>")

    buckets: dict[str, int] = defaultdict(int)
    for value in points:
        bucket_start = int(float(value) // bucket_seconds) * bucket_seconds
        buckets[_format_duration(bucket_start)] += 1

    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(buckets.keys()), y=list(buckets.values()), name="弹幕数量"))
    fig.update_layout(
        title="弹幕密度时间轴",
        xaxis_title="视频内时间",
        yaxis_title="弹幕数量",
        margin=dict(l=40, r=20, t=45, b=40),
        height=360,
    )
    return Markup(
        pio.to_html(
            fig,
            include_plotlyjs=False,
            full_html=False,
            default_width="100%",
            config={"responsive": True, "displaylogo": False},
        )
    )


def count_imported_snapshots(snapshots: Iterable) -> int:
    return sum(1 for row in snapshots if dict(row).get("source_type") == "imported")


def _delta(start: int | None, end: int | None) -> int | str:
    if start is None or end is None:
        return "未知"
    return int(end) - int(start)


def _safe_ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _highlight(value: object) -> Markup:
    return Markup(f"<strong class=\"summary-highlight\">{value}</strong>")


def _bottom_margin(rows: list[dict]) -> int:
    return 72 if count_imported_snapshots(rows) else 44


def _add_source_note(fig: go.Figure, rows: list[dict]) -> None:
    imported_count = count_imported_snapshots(rows)
    if not imported_count:
        return
    fig.add_annotation(
        text=f"说明：图表包含 {imported_count} 条历史导入数据，来源不同于程序自动采集数据。",
        xref="paper",
        yref="paper",
        x=0,
        y=-0.24,
        xanchor="left",
        showarrow=False,
        font=dict(size=12, color="#687586"),
    )


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


def _tokenize(text: str) -> list[str]:
    words: list[str] = []
    for chinese in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if len(chinese) == 2:
            candidates = [chinese]
        else:
            candidates = [chinese[index : index + 2] for index in range(len(chinese) - 1)]
        for token in candidates:
            if token not in STOPWORDS:
                words.append(token)
    for token in re.findall(r"[A-Za-z0-9_]{2,}", text.lower()):
        if token in STOPWORDS:
            continue
        words.append(token)
    return words


def _format_duration(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    return f"{minutes:02d}:{sec:02d}"
