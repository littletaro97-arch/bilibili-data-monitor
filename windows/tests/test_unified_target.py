import pytest,httpx
from app.collectors.task_target import classify_target,resolve_target
from app.models import InvalidBvidError

@pytest.mark.parametrize('text,expected',[
 ('123',('up','123')),('１２３',('up','123')),('HTTPS://SPACE.BILIBILI.COM/123',('up','123')),('UID：123',('up','123')),
 ('https://space.bilibili.com/123/video',('up','123')),
 ('分享 https://space.bilibili.com/123?from=share',('up','123')),
 ('BV1xx411c7mD',('video','BV1xx411c7mD')),
 ('https://www.bilibili.com/video/BV1xx411c7mD/?mid=123',('video','BV1xx411c7mD')),
])
def test_explicit_classification(text,expected):assert classify_target(text)==expected

@pytest.mark.parametrize('text',['0','https://evil.example/BV1xx411c7mD','https://user:pass@www.bilibili.com/video/BV1xx411c7mD','https://space.bilibili.com:123/123','BV1xx411c7mD BV1yy411c7mD'])
def test_invalid_or_ambiguous_targets_rejected(text):
 with pytest.raises(InvalidBvidError):classify_target(text)

@pytest.mark.asyncio
@pytest.mark.parametrize('destination,kind,target',[
 ('https://space.bilibili.com/123','up','123'),
 ('https://www.bilibili.com/video/BV1xx411c7mD','video','BV1xx411c7mD'),
])
async def test_short_link_resolves_before_dispatch(destination,kind,target):
 calls=[]
 def redirect(req):calls.append(str(req.url));return httpx.Response(302,headers={'Location':destination})
 assert await resolve_target('https://b23.tv/Test123',transport=httpx.MockTransport(redirect))==(kind,target)
 assert calls==['https://b23.tv/Test123']

@pytest.mark.asyncio
async def test_short_link_never_follows_untrusted_redirect():
 with pytest.raises(InvalidBvidError):await resolve_target('https://b23.tv/Test123',transport=httpx.MockTransport(lambda req:httpx.Response(302,headers={'Location':'https://evil.example/BV1xx411c7mD'})))

@pytest.mark.asyncio
async def test_unified_endpoint_dispatches_exact_kind_and_preserves_local_login_boundary(monkeypatch):
 from fastapi.testclient import TestClient
 from unittest.mock import AsyncMock
 from app.main import create_app
 app=create_app();video=AsyncMock(return_value='BV1xx411c7mD');up=AsyncMock(return_value=1)
 app.state.video_service.add_video_task=video;app.state.up_monitor.add=up
 client=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')
 assert client.post('/tasks',data={'video_input':'123','interval_seconds':'60','detect_interval':'600'},follow_redirects=False).status_code==303
 up.assert_awaited_once_with('123',600,60);video.assert_not_awaited()
 assert client.post('/tasks',data={'video_input':'BV1xx411c7mD','interval_seconds':'120'},follow_redirects=False).status_code==303
 video.assert_awaited_once_with('BV1xx411c7mD',120)
 remote=TestClient(app,client=('192.168.1.2',9000),base_url='http://127.0.0.1')
 assert remote.post('/tasks',data={'video_input':'123'}).status_code==403
 assert up.await_count==1
