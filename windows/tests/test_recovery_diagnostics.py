from types import SimpleNamespace
from unittest.mock import AsyncMock
import json
import pytest
import httpx
from app.models import RequestFailure,LoginRequiredError,RiskControlError
from app.collectors.bilibili_client import BilibiliClient,request_failure
from app.services.bili_auth import BiliAuth
from app.database import Database,Repository,local_now,parse_iso
from app.models import VideoInfo
from app.services.recovery_service import RecoveryService
from app.up_monitor_store import UpMonitorStore

@pytest.mark.parametrize('exc,kind',[(httpx.ReadTimeout('secret must not leak'),'timeout'),(httpx.ConnectError('secret must not leak'),'network'),(ValueError('secret must not leak'),'parse')])
def test_classification_never_exposes_exception_text(exc,kind):
 failure=request_failure(exc);assert failure.kind==kind and 'secret' not in str(failure)

@pytest.mark.asyncio
async def test_authenticated_invalid_json_is_parse_not_network(monkeypatch):
 original=httpx.AsyncClient
 monkeypatch.setattr('app.collectors.bilibili_client.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(lambda req:httpx.Response(200,text='<html>not json</html>'))))
 with pytest.raises(RequestFailure) as result:
  await BilibiliClient().authenticated_response('https://api.bilibili.com/x/web-interface/nav',{})
 assert result.value.kind=='parse'

@pytest.mark.asyncio
async def test_saved_login_valid_network_unknown_expired_are_distinct_and_retained(tmp_path,monkeypatch):
 monkeypatch.setattr('app.services.bili_auth.protect',lambda value,**kw:value)
 path=tmp_path/'test-auth.dat';content=json.dumps({'cookies':{'SESSDATA':'synthetic-test-only'},'name':'test','account':'1'}).encode();path.write_bytes(content)
 client=SimpleNamespace(authenticated_response=AsyncMock(return_value={'data':{'isLogin':True,'mid':1}}))
 auth=BiliAuth(path,client);assert auth.status()['verification']=='unverified'
 await auth.validate();assert auth.status()['verification']=='valid' and auth.status()['last_verified_at']
 client.authenticated_response.side_effect=RequestFailure('timeout','网络请求超时')
 with pytest.raises(RequestFailure):await auth.validate()
 assert auth.status()['verification']=='unavailable' and auth.status()['saved'] and path.read_bytes()==content
 client.authenticated_response.side_effect=LoginRequiredError('已失效')
 with pytest.raises(LoginRequiredError):await auth.validate()
 assert auth.status()['verification']=='expired' and auth.status()['saved'] and path.read_bytes()==content

@pytest.mark.asyncio
async def test_batch_schedules_network_tasks_preserves_pause_risk_unknown_and_limits(tmp_path):
 db=Database(tmp_path/'recovery.db');db.initialize();repo=Repository(db)
 ids=[]
 for i,bv in enumerate(['BV1xx411c7mD','BV1yy411c7mD','BV1zz411c7mD','BV1ab411c7mD','BV1cd411c7mD']):
  repo.upsert_video(VideoInfo(bv));ids.append(repo.create_task(bv,300,60,10))
 repo.set_task_status(ids[1],'paused');repo.set_task_status(ids[2],'stopped')
 repo.mark_failure('BV1xx411c7mD','timeout',600,failure_kind='timeout')
 repo.mark_failure('BV1ab411c7mD','risk',3600,force_error=True)
 repo.mark_failure('BV1cd411c7mD','legacy unknown',600)
 store=UpMonitorStore(repo);up_id=store.add(123,'test',[],300,60)
 store.fail(up_id,'network',600,'network')
 risk_up=store.add(456,'test',[],300,60);store.fail(risk_up,'risk',3600,'risk')
 crawl=SimpleNamespace(_inflight=set());up=SimpleNamespace(store=store,inflight=set(),video_service=SimpleNamespace(max_active_tasks=10))
 auth=SimpleNamespace(status=lambda:{'saved':True,'verification':'unverified'})
 result=await RecoveryService(repo,crawl,up,auth).run()
 assert result['videos']==1 and result['ups']==1 and result['skipped']==5
 assert repo.get_task(ids[1])['status']=='paused' and repo.get_task(ids[2])['status']=='stopped'
 assert repo.get_task(ids[3])['failure_kind']=='risk' and repo.get_task(ids[3])['cooldown_until']
 assert repo.get_task(ids[4])['cooldown_until']
 assert repo.get_task(ids[0])['cooldown_until'] is None and store.get(up_id)['cooldown_until'] is None
 assert store.get(risk_up)['cooldown_until']


def test_repeated_network_failures_keep_auto_schedule_running(tmp_path):
 db=Database(tmp_path/'tasks.db');db.initialize();repo=Repository(db);bv='BV1xx411c7mD'
 repo.upsert_video(VideoInfo(bv));identity=repo.create_task(bv,300,60,10)
 for _ in range(4):repo.mark_failure(bv,'连接失败',600,failure_kind='network')
 assert repo.get_task(identity)['status']=='running' and repo.get_task(identity)['consecutive_failures']==4
 repo.mark_failure(bv,'平台限制',3600,force_error=True)
 assert repo.get_task(identity)['status']=='error' and repo.get_task(identity)['failure_kind']=='risk'

@pytest.mark.asyncio
async def test_up_cooldown_manual_action_explains_skip(tmp_path):
 from app.services.up_monitor_service import UpMonitorService
 db=Database(tmp_path/'up.db');db.initialize();repo=Repository(db);provider=SimpleNamespace(page=AsyncMock())
 up=UpMonitorService(repo,provider,SimpleNamespace(min_interval=60),None)
 identity=up.store.add(123,'test',[],300,60);up.store.fail(identity,'连接失败',600,'network')
 result=await up.poll(identity)
 assert '冷却' in result['skipped'] and '自动重试' in result['skipped'];provider.page.assert_not_awaited()

@pytest.mark.skipif(__import__('os').environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in browser')
def test_cleanup_auth_verification_and_cooldown_display(tmp_path,monkeypatch):
 from urllib.parse import urlsplit
 from fastapi.testclient import TestClient
 from playwright.sync_api import sync_playwright,expect
 from app.main import create_app
 from app.services.bili_auth import BiliAuth
 db=Database(tmp_path/'ui.db');db.initialize();repo=Repository(db);bv='BV1xx411c7mD'
 repo.upsert_video(VideoInfo(bv,title='恢复测试'));task=repo.create_task(bv,300,60,10)
 repo.mark_failure(bv,'连接失败',600,failure_kind='network')
 app=create_app();app.state.repository=repo
 auth=BiliAuth(tmp_path/'absent-auth.dat',SimpleNamespace(authenticated_response=AsyncMock(return_value={'data':{'isLogin':True,'mid':1}})))
 auth.cookies={'SESSDATA':'synthetic-test-only'};app.state.bili_auth=auth
 client=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')
 def serve(route):
  req=route.request;response=client.request(req.method,urlsplit(req.url).path,content=req.post_data,headers={'Content-Type':req.headers.get('content-type','')})
  route.fulfill(status=response.status_code,headers={k:v for k,v in response.headers.items() if k.lower() not in {'content-length','content-encoding'}},body=response.content)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True)
  try:
   page=browser.new_page();page.route('**/*',serve);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1/');expect(page.locator('[data-cooldown-until]')).to_contain_text('冷却剩余约')
   expect(page.get_by_role('button',name='一键重启检测')).to_be_visible()
   page.goto('http://127.0.0.1/settings');expect(page.locator('#bili-auth-status')).to_contain_text('尚未向平台验证')
   page.locator('#bili-verify').click();expect(page.locator('#bili-auth-status')).to_contain_text('平台验证有效')
   page.goto('http://127.0.0.1/videos/'+bv)
   assert page.locator('[data-chart-panel=text-import]').count()==0 and page.locator('#text-collect-form').count()==0
   assert page.locator('#full-text-control').count()==1 and not errors
  finally:browser.close()
