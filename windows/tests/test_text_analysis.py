from app.services.analysis_service import build_danmaku_density_chart, build_dual_axis_chart, build_ratio_chart, top_words


class Row(dict):
    pass


def test_top_words_counts_chinese_and_english_tokens():
    rows = [
        Row(message="这个视频很好 很好 test"),
        Row(message="很好 test test"),
        Row(message="的 了 是"),
    ]

    result = top_words(rows, field="message", limit=3)

    assert result[0] == {"word": "很好", "count": 3}
    assert result[1] == {"word": "test", "count": 3}


def test_danmaku_density_chart_handles_empty_rows():
    html = str(build_danmaku_density_chart([]))
    assert "暂无足够弹幕时间数据" in html


def test_danmaku_density_chart_builds_plotly_bar():
    rows = [
        Row(progress_sec=1.0),
        Row(progress_sec=12.0),
        Row(progress_sec=35.0),
    ]

    html = str(build_danmaku_density_chart(rows, bucket_seconds=30))

    assert "Plotly.newPlot" in html
    assert "00:00" in html
    assert "00:30" in html


def test_dual_axis_chart_handles_empty_rows():
    html = str(build_dual_axis_chart([]))
    assert "至少需要 2 条快照" in html


def test_dual_axis_chart_builds_plotly_lines():
    rows = [
        Row(captured_at="2026-06-29T10:00:00+08:00", view_count=100, like_count=5),
        Row(captured_at="2026-06-29T11:00:00+08:00", view_count=160, like_count=9),
    ]

    html = str(build_dual_axis_chart(rows, "view_count", "like_count"))

    assert "Plotly.newPlot" in html
    assert "\\u64ad\\u653e\\u91cf" in html
    assert "\\u70b9\\u8d5e\\u6570" in html
    assert "y2" in html


def test_ratio_chart_builds_plotly_lines():
    rows = [
        Row(captured_at="2026-06-29T10:00:00+08:00", view_count=100, like_count=5, source_type="collected"),
        Row(captured_at="2026-06-29T11:00:00+08:00", view_count=200, like_count=20, source_type="imported"),
    ]

    html = str(build_ratio_chart(rows, "like_count", "view_count"))

    assert "Plotly.newPlot" in html
    assert "y2" in html
    assert "0.1" in html
    assert "\\u5386\\u53f2\\u5bfc\\u5165" in html
