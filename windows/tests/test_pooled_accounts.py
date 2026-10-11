import asyncio,json,ssl
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from app.collectors.bilibili_client import BilibiliClient
from app.services.account_pool import AccountPool,ProfileClient
from app.services.bili_auth import BiliAuth
from app.database import iso_now
from app.models import LoginRequiredError,RiskControlError,RequestFailure,StaleJobError,DanmakuItem,ProviderError
from tests.test_full_text import setup,BV


def accounts(tmp_path,backup=True,primary=True):
    engine=BilibiliClient(min_interval_seconds=0)
    items=[]
    for key,enabled,uid in [('primary',primary,'101'),('backup',backup,'202')]:
        a=BiliAuth(tmp_path/(key+'-auth.dat'),ProfileClient(engine,key))
        a.cookies={'SESSDATA':'mock-'+key} if enabled else {};a.account=uid if enabled else ''
        a.verification='valid' if enabled else 'unverified';a.last_verified_at=iso_now() if enabled else None
        a.validate=AsyncMock(return_value={'isLogin':True,'mid':int(uid),'wbi_img':{'img_url':'https://x/'+('a'*32)+'.png','sub_url':'https://x/'+('b'*32)+'.png'}})
        items.append(a)
    return AccountPool(*items)

@pytest.mark.asyncio
async def test_http_pool_reuses_sessions_ssl_and_isolates_cookies(monkeypatch):
    actual=httpx.AsyncClient;create=ssl.create_default_context;created=[];contexts=[];seen=[]
    def context(**kw):value=create(**kw);contexts.append(value);return value
    monkeypatch.setattr(ssl,'create_default_context',context)
    def respond(request):
        seen.append((request.url.path,request.headers.get('cookie','')))
        return httpx.Response(200,json={'code':0},headers={'set-cookie':'SESSDATA=mock-stale; Path=/'})
    def factory(**kw):
        created.append(kw['verify']);return actual(transport=httpx.MockTransport(respond),**kw)
    monkeypatch.setattr(httpx,'AsyncClient',factory)
    engine=BilibiliClient(min_interval_seconds=0)
    for _ in range(2):
        await engine.authenticated_response('https://api.bilibili.com/primary',{'SESSDATA':'mock-A'},profile_key='primary')
        await engine.authenticated_response('https://api.bilibili.com/backup',{'SESSDATA':'mock-B'},profile_key='backup')
        await engine.get_json('https://api.bilibili.com/public')
    assert len(created)==3 and len(contexts)==1 and all(c is contexts[0] for c in created)
    assert all(('mock-A' in cookie and 'mock-B' not in cookie and 'mock-stale' not in cookie) for path,cookie in seen if path=='/primary')
    assert all(('mock-B' in cookie and 'mock-A' not in cookie) for path,cookie in seen if path=='/backup')
    assert all(not cookie for path,cookie in seen if path=='/public')
    sessions=list(engine._sessions.values());await engine.close();assert all(s.is_closed for s in sessions)

@pytest.mark.asyncio
async def test_shared_risk_blocks_other_account(monkeypatch):
    actual=httpx.AsyncClient;calls=[]
    def respond(r):calls.append(r.url.path);return httpx.Response(429,json={})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(transport=httpx.MockTransport(respond),**kw))
    engine=BilibiliClient(min_interval_seconds=0)
    with pytest.raises(RiskControlError):await engine.authenticated_response('https://api.bilibili.com/A',{},profile_key='primary')
    with pytest.raises(RiskControlError):await engine.authenticated_response('https://api.bilibili.com/B',{},profile_key='backup')
    assert calls==['/A'];await engine.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('primary,backup',[(True,False),(False,True)])
async def test_one_account_in_either_slot_can_capture(tmp_path,primary,backup):
    repo,s,_,p=setup(tmp_path);s.auth=accounts(tmp_path,backup=backup,primary=primary)
    j=await s.start(BV,'danmaku','selected',10);await s.task
    assert s.load(j['id'])['status']=='complete'
    assert s.load(j['id'])['state']['owner_profile']==('primary' if primary else 'backup')

@pytest.mark.asyncio
async def test_expiry_handoff_keeps_segment_and_fences_old_save(tmp_path):
    repo,s,_,p=setup(tmp_path,budget=1);s.auth=pool=accounts(tmp_path)
    calls=[]
    async def segment(bvid,cid,index):
        key=pool.current_key();calls.append((key,index))
        if key=='primary' and index==2:raise LoginRequiredError('expired')
        return [DanmakuItem(BV,10,index,'sample',1,source_id=str(index))]
    p.segment=segment
    j=await s.start(BV,'danmaku','selected',10);await s.task
    old=s.load(j['id']);assert old['state']['segment']==2
    await s.resume(j['id']);await s.task
    assert s.load(j['id'])['status']=='waiting_login'
    await s.pump();await s.task
    saved=s.load(j['id']);assert saved['status']=='complete'
    assert saved['state']['handoffs']==1 and saved['state']['created_owner']=='101'
    assert calls==[('primary',1),('primary',2),('backup',2)]
    assert len(repo.list_danmaku(BV))==2
    with pytest.raises(StaleJobError):s.save(old)
    pool.profiles['primary'].verification='valid'
    assert saved['state']['owner_profile']=='backup'

@pytest.mark.asyncio
async def test_risk_does_not_handoff(tmp_path):
    repo,s,_,p=setup(tmp_path);s.auth=pool=accounts(tmp_path)
    p.segment=AsyncMock(side_effect=RiskControlError('limit'))
    j=await s.start(BV,'danmaku','selected',10);await s.task
    saved=s.load(j['id']);assert saved['state']['failure_kind']=='risk'
    assert saved['state'].get('handoffs',0)==0 and saved['state']['owner_profile']=='primary'
    assert pool.profiles['backup'].validate.await_count==0

@pytest.mark.asyncio
async def test_content_401_requires_account_validation(tmp_path):
    pool=accounts(tmp_path);token=pool.bind('primary')
    try:
        with pytest.raises(RequestFailure,match='访问被拒绝'):await pool.expired(LoginRequiredError('401',confirmed=False))
        assert pool.profiles['primary'].verification=='valid'
    finally:pool.unbind(token)

@pytest.mark.asyncio
async def test_duplicate_login_is_rejected_before_file_write(tmp_path):
    pool=accounts(tmp_path)
    backup=pool.profiles['backup'];backup.validate=AsyncMock(return_value={'mid':101,'isLogin':True})
    with pytest.raises(ProviderError,match='不同账户'):await backup.save({'SESSDATA':'mock-duplicate'})
    assert not backup.path.exists() and backup.account=='202'


@pytest.mark.asyncio
async def test_up_retries_same_page_with_backup_on_expiry(tmp_path,monkeypatch):
    from app.collectors.up_provider import UpVideoProvider
    pool=accounts(tmp_path);pool.preferred=lambda target:'primary'
    engine=pool.profiles['primary'].client.engine;actual=httpx.AsyncClient;seen=[]
    def respond(request):
        key=request.headers.get('cookie','');seen.append((key,request.url.params['pn']))
        if 'mock-primary' in key:return httpx.Response(200,json={'code':-101})
        return httpx.Response(200,json={'code':0,'data':{'list':{'vlist':[]},'page':{'count':0}}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(transport=httpx.MockTransport(respond),**kw))
    p=UpVideoProvider(pool.client,pool)
    assert await p.page(123,2)==([],0)
    assert len(seen)==2 and [x[1] for x in seen]==['2','2']
    assert 'mock-primary' in seen[0][0] and 'mock-backup' in seen[1][0]
    await engine.close()

@pytest.mark.asyncio
async def test_explicit_logout_resumes_at_saved_segment(tmp_path):
    repo,s,_,p=setup(tmp_path);s.auth=pool=accounts(tmp_path)
    entered=asyncio.Event()
    async def segment(*args):entered.set();await asyncio.Event().wait()
    p.segment=segment
    j=await s.start(BV,'danmaku','selected',10);await entered.wait()
    await s.account_exit('primary');await pool.profiles['primary'].logout()
    assert not s.load(j['id'])['state']['manual_pause']
    p.segment=AsyncMock(return_value=[])
    await s.pump();await s.task
    assert s.load(j['id'])['status']=='complete'
    assert s.load(j['id'])['state']['owner_profile']=='backup'
    assert p.segment.call_args_list[0].args==(BV,10,1)

@pytest.mark.asyncio
async def test_shared_interval_is_start_based(monkeypatch):
    import app.collectors.bilibili_client as module
    actual=httpx.AsyncClient;clock=[10.0];starts=[]
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    async def sleep(seconds):clock[0]+=seconds
    monkeypatch.setattr(module.asyncio,'sleep',sleep)
    def respond(request):starts.append(clock[0]);return httpx.Response(200,json={'code':0})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(transport=httpx.MockTransport(respond),**kw))
    engine=BilibiliClient(min_interval_seconds=.75)
    await engine.get_json('https://api.bilibili.com/public')
    await engine.authenticated_response('https://api.bilibili.com/primary',{},profile_key='primary')
    await engine.authenticated_response('https://api.bilibili.com/backup',{},profile_key='backup')
    assert starts==[10,10.75,11.5]
    await engine.close()


def test_two_profile_login_ui_backup_is_optional(tmp_path):
    from urllib.parse import urlsplit
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright,expect
    from app.main import create_app
    pool=accounts(tmp_path,backup=False);pool.profiles['primary'].name='测试主账号'
    pool.profiles['backup'].qrcode=AsyncMock(return_value={'image':'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jLzYAAAAASUVORK5CYII='})
    async def poll():
        a=pool.profiles['backup'];a.cookies={'SESSDATA':'mock-backup'};a.account='202';a.name='测试备用账号';a.verification='valid';a.last_verified_at=iso_now()
        return {'status':'ok',**a.status()}
    pool.profiles['backup'].poll=poll
    app=create_app();app.state.bili_auth=pool
    app.state.full_text=SimpleNamespace(lock=asyncio.Lock(),task=None,account_exit=AsyncMock())
    client=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1');requests=[]
    def serve(route):
        r=route.request;path=urlsplit(r.url).path
        if r.method=='POST' and path.startswith('/api/text/auth'):requests.append((path,json.loads(r.post_data or '{}')))
        response=client.request(r.method,path,content=r.post_data,headers={'content-type':r.headers.get('content-type','')})
        route.fulfill(status=response.status_code,headers={k:v for k,v in response.headers.items() if k.lower() not in {'content-length','content-encoding'}},body=response.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1500,'height':900});page.route('**/*',serve);errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1/settings')
            expect(page.locator('#bili-auth-status')).to_contain_text('测试主账号')
            expect(page.locator('#bili-profile-summary')).to_contain_text('备用账号：未登录')
            left=page.locator('#runtime-settings').bounding_box();right=page.locator('#bili-account').bounding_box()
            assert abs(left['height']-right['height'])<2
            assert page.locator('.runtime-table').bounding_box()['height']>380
            page.locator('.manual-session > summary').click()
            page.wait_for_function('!document.querySelector(".manual-session > .details-body").getAnimations().length')
            assert abs(page.locator('#runtime-settings').bounding_box()['height']-page.locator('#bili-account').bounding_box()['height'])<2
            page.set_viewport_size({'width':600,'height':900})
            page.locator('#bili-profile-backup').click()
            expect(page.locator('#bili-auth-status')).to_contain_text('尚未登录')
            page.locator('#bili-qr').click()
            expect(page.locator('#bili-auth-status')).to_contain_text('测试备用账号')
            assert requests[0][1]['profile']=='backup'
            page.locator('#bili-logout').click()
            expect(page.locator('#bili-auth-status')).to_contain_text('尚未登录')
            assert pool.profiles['primary'].cookies
            assert app.state.full_text.account_exit.call_args.args==('backup',)
            page.goto('http://127.0.0.1/')
            page.get_by_role('link',name='访问设置',exact=True).click()
            expect(page).to_have_url('http://127.0.0.1/settings#lan-access')
            page.wait_for_load_state('load')
            page.wait_for_function('document.querySelector("main").getAnimations().length===0')
            assert -2<=page.locator('#lan-access').bounding_box()['y']<900
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and not errors
        finally:browser.close()


@pytest.mark.asyncio
async def test_handoff_rejected_cursor_restarts_once_and_preserves_roots(tmp_path):
    from app.models import CommentCursorError
    repo,s,_,p=setup(tmp_path,budget=1);s.auth=pool=accounts(tmp_path)
    pool.profiles['primary'].verification='expired'
    job={'id':'migration-test','bvid':BV,'kind':'comments','status':'queued','message':'test',
         'state':{'owner':'101','owner_profile':'primary','parts':[{'cid':10,'page':1,'duration':720}],
                  'total_parts':1,'aid':123,'scope':'shared','part_index':0,'segment':1,'offset':'old-cursor','pending':None,
                  'responses':1,'received':0,'saved_new':0,'counts_version':1,'queued_manual':True}}
    s.save(job);s.root_done(job['id'],'old-root',mark=True)
    p.roots=AsyncMock(side_effect=[CommentCursorError('bad cursor'),{'replies':[],'cursor':{'is_end':True}}])
    await s.pump();await s.task
    checkpoint=s.load(job['id'])
    assert checkpoint['state']['owner_profile']=='backup' and checkpoint['state']['offset']==''
    assert s.root_done(job['id'],'old-root')
    await s.pump();await s.task
    assert s.load(job['id'])['status']=='complete'
    assert [call.args[1] for call in p.roots.call_args_list]==['old-cursor','']
