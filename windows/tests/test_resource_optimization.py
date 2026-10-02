import asyncio
from io import BytesIO
import json
import re

import httpx
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.cover import CoverCache, cover_key, local_cover_url
from app.services.analysis_service import build_dual_axis_chart

URL = 'https://i0.hdslb.com/bfs/archive/example.jpg'

def image_bytes():
    output = BytesIO()
    Image.new('RGB', (1920, 1080), 'pink').save(output, 'JPEG')
    return output.getvalue()

@pytest.mark.asyncio
async def test_cache_deduplicates_and_survives_new_instance(tmp_path):
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=image_bytes(), headers={'content-type': 'image/jpeg'})
    transport = httpx.MockTransport(respond)
    cache = CoverCache(tmp_path, transport)
    paths = await asyncio.gather(*(cache.get(URL) for _ in range(6)))
    assert len(set(paths)) == 1 and calls == [URL]
    assert await CoverCache(tmp_path, transport).get(URL) == paths[0]
    assert calls == [URL]
    with Image.open(paths[0]) as image:
        assert image.size == (960, 540)
    assert local_cover_url('BV1xx411c7mD', URL) != local_cover_url('BV1xx411c7mD', URL + '?v=2')

@pytest.mark.asyncio
@pytest.mark.parametrize('response', [
    httpx.Response(302, headers={'location': 'https://127.0.0.1/secret'}),
    httpx.Response(200, content=b'bad', headers={'content-type': 'text/html'}),
    httpx.Response(200, content=b'bad', headers={'content-type': 'image/jpeg', 'content-length': str(6 * 1024 * 1024)}),
    httpx.Response(200, content=b'bad', headers={'content-type': 'image/jpeg'}),
])
async def test_rejects_redirects_invalid_images_and_oversize(tmp_path, response):
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return response
    with pytest.raises((ValueError, OSError)):
        await CoverCache(tmp_path, httpx.MockTransport(respond)).get(URL)
    assert calls == [URL] and not list(tmp_path.glob('*.webp'))

@pytest.mark.asyncio
async def test_cache_quota_evicts_old_entries(tmp_path):
    cache = CoverCache(tmp_path, httpx.MockTransport(lambda request: httpx.Response(200, content=image_bytes(), headers={'content-type': 'image/jpeg'})))
    cache.MAX_FILES = 2
    await cache.get(URL)
    await cache.get(URL + '?v=2')
    await cache.get(URL + '?v=3')
    assert len(list(tmp_path.glob('*.webp'))) == 2
    assert not (tmp_path / (cover_key(URL) + '.webp')).exists()

def test_cover_endpoint_uses_metadata_bound_key_and_revalidates(tmp_path):
    from app.main import create_app
    from app.database import Database, Repository
    from app.models import VideoInfo
    db = Database(tmp_path / 'data.db'); db.initialize()
    repo = Repository(db)
    repo.upsert_video(VideoInfo('BV1xx411c7mD', title='test', cover_url=URL))
    app = create_app(); app.state.repository = repo
    app.state.cover_cache = CoverCache(tmp_path / 'cache', httpx.MockTransport(lambda request: httpx.Response(200, content=image_bytes(), headers={'content-type': 'image/jpeg'})))
    client = TestClient(app, client=('127.0.0.1', 9000), base_url='http://127.0.0.1')
    url = local_cover_url('BV1xx411c7mD', URL)
    response = client.get(url)
    assert response.status_code == 200 and response.headers['content-type'] == 'image/webp'
    assert client.get(url, headers={'If-None-Match': response.headers['etag']}).status_code == 304
    assert client.get('/covers/BV1xx411c7mD/wrong.webp').status_code == 404
    repo.update_video_cover('BV1xx411c7mD', URL + '?new')
    assert client.get(url).status_code == 404
    assert client.get('/assets/plotly.min.js').headers['cache-control'] == 'public, max-age=86400'

def test_lazy_chart_json_is_safe_and_reports_remain_standalone():
    rows = [{'captured_at': value, 'view_count': i, 'like_count': i} for i, value in enumerate(['2026-10-01', '</script><script>evil()</script>'])]
    lazy = str(build_dual_axis_chart(rows, lazy=True))
    assert 'Plotly.newPlot' not in lazy and '</script><script>evil' not in lazy
    payload = re.search(r'data-chart-json>(.*?)</script>', lazy).group(1)
    assert json.loads(payload)['data'][0]['x'][1] == rows[1]['captured_at']
    assert 'Plotly.newPlot' in str(build_dual_axis_chart(rows, include_plotlyjs=True))
