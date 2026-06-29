from app.services.analysis_service import build_danmaku_density_chart, top_words


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
