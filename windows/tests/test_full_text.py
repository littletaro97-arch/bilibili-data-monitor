import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.collectors.full_text import sign, segment_message, decode_segment, FullTextProvider
from app.database import Database, Repository
from app.models import VideoInfo, DanmakuItem, ProviderError, RiskControlError
from app.services.bili_auth import BiliAuth, protect
from app.services.full_text_service import FullTextService
from app.ui.full_text_api import router

BV='BV1xx411c7mD'


def setup(tmp_path,provider=None,budget=150):
    db=Database(tmp_path/'test.db');db.initialize();repo=Repository(db)
    repo.upsert_video(VideoInfo(BV,aid=123,cid=10))
    auth=SimpleNamespace(cookies={'SESSDATA':'test-secret'},account='123',validate=AsyncMock(return_value={'mid':123,'isLogin':True}))
    provider=provider or SimpleNamespace(view=AsyncMock(return_value=(123,[{'cid':10,'page':1,'duration':720,'name':'P1'}])),
        segment=AsyncMock(return_value=[]),keys=None)
    service=FullTextService(repo,provider,auth,budget=budget)
    return repo,service,auth,provider


def test_wbi_known_vector():
    result=sign({'foo':'114','bar':'514','zab':1919810},'7cd084941338484aae1ad9425b84077c','4932caff0ff746eab6f01bf08b70ac45',1702204169)
    assert result['w_rid']=='8f6f2b5b3d485fe1886cec6a0be8c5d4'
    assert sign({'x':"!'()*hello"},'a'*32,'b'*32,1)['x']=='hello'


def test_protobuf_id_precision_and_invalid():
    msg=segment_message()();msg.elems.add(id=9007199254740993,progress=1250,content='弹幕',ctime=1710)
    rows=decode_segment(msg.SerializeToString(),BV,10)
    assert rows[0].source_id=='9007199254740993' and rows[0].progress_sec==1.25
    assert decode_segment(b'',BV,10)==[]
    with pytest.raises(ProviderError): decode_segment(b'<html>',BV,10)


@pytest.mark.asyncio
async def test_empty_segment_does_not_stop_and_resume_dedup(tmp_path):
    repo,s,auth,p=setup(tmp_path,budget=1)
    p.segment.side_effect=[[],[DanmakuItem(BV,10,370,'later',1,source_id='99')]]
    j=await s.start(BV,'danmaku','selected',10);await s.task
    assert s.load(j['id'])['status']=='paused' and s.load(j['id'])['state']['segment']==2
    await s.resume(j['id']);await s.task
    assert s.load(j['id'])['status']=='complete' and repo.list_danmaku(BV)[0]['text']=='later'
    assert p.segment.call_args_list[1].args==(BV,10,2)
    assert s.save_dm([DanmakuItem(BV,10,370,'later',1,source_id='99')])==0
    assert len(repo.list_danmaku(BV))==1
    assert repo.text_dashboard_data(BV)['runs'][0]['metadata']['complete'] is False


@pytest.mark.asyncio
async def test_selected_and_all_parts(tmp_path):
    repo,s,a,p=setup(tmp_path)
    p.view.return_value=(123,[{'cid':10,'page':1,'duration':1,'name':'one'},{'cid':11,'page':2,'duration':1,'name':'two'}])
    await s.start(BV,'danmaku','selected',11);await s.task
    assert p.segment.call_args.args==(BV,11,1)
    p.segment.reset_mock();await s.start(BV,'danmaku','all',10);await s.task
    assert [c.args[1] for c in p.segment.call_args_list]==[10,11]
    with pytest.raises(ProviderError): await s.start(BV,'danmaku','selected',999)


def root(identity,children=0,parent=None):
    return {'rpid_str':identity,'rcount':children,'parent_str':parent,'content':{'message':'文本'+identity},'member':{'uname':'作者'}}


@pytest.mark.asyncio
async def test_comments_children_pagination_and_pinned_dedup(tmp_path):
    repo,s,a,p=setup(tmp_path,budget=2)
    p.roots=AsyncMock(side_effect=[{'replies':[root('1',21)],'cursor':{'is_end':False,'pagination_reply':{'next_offset':'next'}}},
        {'replies':[root('2')],'top_replies':[root('1',21)],'cursor':{'is_end':True}}])
    p.children=AsyncMock(side_effect=[{'page':{'num':1,'size':20,'count':21},'replies':[root(str(i),parent='1') for i in range(10,30)]},
        {'page':{'num':2,'size':20,'count':21},'replies':[root('30',parent='10')]}])
    j=await s.start(BV,'comments','selected',10);await s.task
    assert s.load(j['id'])['state']['pending']['page']==2
    await s.resume(j['id']);await s.task
    while s.load(j['id'])['status']=='paused': await s.resume(j['id']);await s.task
    assert len(repo.list_comments(BV,100))==23 and p.children.await_count==2
    assert next(r for r in repo.list_comments(BV,100) if r['rpid']=='30')['parent_rpid']=='10'
    assert s.load(j['id'])['status']=='complete'


@pytest.mark.asyncio
async def test_bad_cursor_never_claims_complete(tmp_path):
    repo,s,a,p=setup(tmp_path)
    p.roots=AsyncMock(return_value={'replies':[root('1')],'cursor':{'is_end':False,'pagination_reply':{'next_offset':''}}})
    j=await s.start(BV,'comments','all',0);await s.task
    assert s.load(j['id'])['status']=='paused' and '游标' in s.load(j['id'])['message']
    assert len(repo.list_comments(BV))==1


@pytest.mark.asyncio
async def test_risk_cooldown_restart_and_account_binding(tmp_path):
    repo,s,a,p=setup(tmp_path);p.segment.side_effect=RiskControlError('secret must not persist')
    j=await s.start(BV,'danmaku','selected',10);await s.task
    saved=s.load(j['id']);assert saved['status']=='paused' and 'secret' not in json.dumps(saved)
    with pytest.raises(ProviderError,match='冷却'): await s.resume(j['id'])
    with pytest.raises(ProviderError,match='冷却'): await s.start(BV,'danmaku','all',0)
    saved['state']['retry_at']=0;s.save(saved)
    with repo.database.connect() as c: c.execute("UPDATE text_job_control SET value=0")
    a.account='other'
    with pytest.raises(ProviderError,match='账户'): await s.resume(j['id'])
    saved['status']='running';s.save(saved)
    restored=FullTextService(repo,p,a);assert restored.load(j['id'])['status']=='paused'


@pytest.mark.asyncio
async def test_cancel_keeps_next_segment(tmp_path):
    repo,s,a,p=setup(tmp_path);entered=asyncio.Event()
    async def segment(*args): entered.set();await asyncio.Event().wait()
    p.segment.side_effect=segment
    j=await s.start(BV,'danmaku','selected',10);await entered.wait()
    with pytest.raises(ProviderError,match='已有'): await s.start(BV,'danmaku','selected',10)
    await s.cancel(j['id']);assert s.load(j['id'])['state']['segment']==1 and s.load(j['id'])['status']=='paused'


@pytest.mark.asyncio
async def test_recycle_stops_collection_and_blocks_resume(tmp_path):
    repo,s,a,p=setup(tmp_path);task_id=repo.create_task(BV,60,60,10);entered=asyncio.Event()
    async def segment(*args): entered.set();await asyncio.Event().wait()
    p.segment.side_effect=segment
    j=await s.start(BV,'danmaku','selected',10);await entered.wait()
    repo.set_task_status(task_id,'stopped');await s.cancel_video(BV)
    assert s.load(j['id'])['status']=='paused'
    with pytest.raises(ProviderError,match='回收站'): await s.resume(j['id'])
    with pytest.raises(ProviderError,match='回收站'): await s.start(BV,'danmaku','all',0)
    repo.set_task_status(task_id,'running');p.segment.side_effect=None
    await s.resume(j['id']);await s.task;assert s.load(j['id'])['status']=='complete'


@pytest.mark.asyncio
async def test_completed_checkpoint_does_not_restart_comments(tmp_path):
    repo,s,a,p=setup(tmp_path)
    p.roots=AsyncMock(return_value={'replies':[],'cursor':{'is_end':True}})
    j=await s.start(BV,'comments','selected',10);await s.task
    saved=s.load(j['id']);saved['status']='paused';s.save(saved)
    await s.resume(j['id']);await s.task
    assert p.roots.await_count==1 and s.load(j['id'])['status']=='complete'


@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI')
@pytest.mark.asyncio
async def test_dpapi_save_and_no_cookie_in_status(tmp_path):
    secret='mock-private-secret';path=tmp_path/'auth.dat'
    client=SimpleNamespace(authenticated_response=AsyncMock(return_value={'data':{'isLogin':True,'mid':123,'uname':'测试'}}))
    auth=BiliAuth(path,client);await auth.save_sessdata(secret)
    assert secret.encode() not in path.read_bytes() and secret not in json.dumps(auth.status())
    assert protect(protect(b'roundtrip'),decrypt=True)==b'roundtrip'
    reloaded=BiliAuth(path,client);assert reloaded.cookies['SESSDATA']==secret
    await reloaded.logout();assert not path.exists()


@pytest.mark.asyncio
async def test_qr_nested_status_and_cookie_received(tmp_path):
    client=SimpleNamespace(user_agent='test',authenticated_response=AsyncMock(return_value={'data':{'isLogin':True,'mid':123,'uname':'测试'}}))
    auth=BiliAuth(tmp_path/'auth.dat',client)
    def response(request):
        if request.url.path.endswith('generate'): return httpx.Response(200,json={'code':0,'data':{'url':'https://passport.bilibili.com/test','qrcode_key':'private-key'}})
        return httpx.Response(200,json={'code':0,'data':{'code':0}},headers={'set-cookie':'SESSDATA=qr-secret; Domain=.bilibili.com; Path=/; Secure'})
    auth._passport=httpx.AsyncClient(transport=httpx.MockTransport(response))
    result=await auth.qrcode();assert result['image'].startswith('data:image/png;') and 'private-key' not in json.dumps(result)
    polled=await auth.poll();assert polled['status']=='ok' and auth.cookies['SESSDATA']=='qr-secret'
    assert 'qr-secret' not in json.dumps(polled)
    await auth.close()


def test_auth_routes_local_origin_and_no_secrets(tmp_path):
    repo,s,a,p=setup(tmp_path);app=FastAPI();app.include_router(router);app.state.full_text=s
    app.state.bili_auth=SimpleNamespace(status=lambda:{'saved':False,'message':'未登录'})
    local=TestClient(app,client=('127.0.0.1',8000),base_url='http://127.0.0.1')
    assert local.get('/api/text/auth').status_code==200
    assert local.post('/api/text/auth/qr',headers={'Origin':'https://evil.example'}).status_code==403
    assert local.get('/api/text/auth',headers={'Host':'evil.example'}).status_code==403
    remote=TestClient(app,client=('192.168.1.2',8000));assert remote.get('/api/text/auth').status_code==403


@pytest.mark.asyncio
async def test_full_provider_wires_signing_and_parsing():
    calls=[]
    async def request(url,cookies,params=None,**kw):
        calls.append((url,params,kw));return {'data':{'cursor':{'is_end':True}}}
    auth=SimpleNamespace(cookies={'SESSDATA':'test'},validate=AsyncMock(return_value={'wbi_img':{'img_url':'https://i0.hdslb.com/bfs/wbi/'+'a'*32+'.png','sub_url':'https://i0.hdslb.com/bfs/wbi/'+'b'*32+'.png'}}))
    p=FullTextProvider(SimpleNamespace(authenticated_response=request),auth)
    await p.roots(123,'');assert calls[0][1]['w_rid'] and calls[0][1]['mode']=='2'
    assert json.loads(calls[0][1]['pagination_str'])=={'offset':''}


def test_export_streams_iterator(tmp_path):
    import csv
    from app.services.export_service import _write_csv
    target=tmp_path/'rows.csv'
    _write_csv(target,({'id':str(i),'text':'内容'} for i in range(5000)))
    with target.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==5000 and rows[-1]['id']=='4999'


@pytest.mark.asyncio
@pytest.mark.parametrize('status,payload,error',[(403,{},RiskControlError),(200,{'code':-101},RiskControlError),(200,{'code':-400,'message':'private-secret'},ProviderError),(200,[],ProviderError),(304,{},ProviderError)])
async def test_authenticated_transport_errors_are_not_data(monkeypatch,status,payload,error):
    from app.collectors.bilibili_client import BilibiliClient
    actual=httpx.AsyncClient
    transport=httpx.MockTransport(lambda r:httpx.Response(status,json=payload))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(transport=transport,**kw))
    with pytest.raises(error) as caught:
        await BilibiliClient().authenticated_response('https://api.bilibili.com/test',{'SESSDATA':'private-secret'})
    assert 'private-secret' not in str(caught.value)


@pytest.mark.asyncio
async def test_credentials_cannot_be_sent_off_platform():
    from app.collectors.bilibili_client import BilibiliClient
    for url in ['http://api.bilibili.com/test','https://evil.example/test','https://api.bilibili.com@evil.example/test']:
        with pytest.raises(ProviderError): await BilibiliClient().authenticated_response(url,{'SESSDATA':'private-secret'})


@pytest.mark.asyncio
async def test_cursor_cycle_stops_without_duplicate_growth(tmp_path):
    repo,s,a,p=setup(tmp_path)
    p.roots=AsyncMock(side_effect=[{'replies':[],'cursor':{'is_end':False,'pagination_reply':{'next_offset':'A'}}},
        {'replies':[],'cursor':{'is_end':False,'pagination_reply':{'next_offset':'B'}}},
        {'replies':[],'cursor':{'is_end':False,'pagination_reply':{'next_offset':'A'}}}])
    j=await s.start(BV,'comments','selected',10);await s.task
    assert s.load(j['id'])['status']=='paused' and '循环' in s.load(j['id'])['message']
    assert p.roots.await_count==3


@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in headless browser')
def test_login_and_job_frontend(tmp_path):
    from urllib.parse import urlsplit
    from playwright.sync_api import sync_playwright,expect
    from app.main import create_app
    repo,s,a,p=setup(tmp_path)
    app=create_app();app.state.repository=repo
    status={'saved':False,'name':'','message':'尚未登录'}
    image='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jLzYAAAAASUVORK5CYII='
    class Auth:
        def status(self):return dict(status)
        async def qrcode(self):return {'image':image}
        async def poll(self):status.update(saved=True,name='测试账户',message='已保存');return {'status':'ok',**status}
        async def logout(self):status.update(saved=False,name='',message='尚未登录')
    current={'job':None};calls=[]
    class Service:
        lock=asyncio.Lock()
        def idle(self):pass
        def latest(self,bvid):return current['job']
        def load(self,identity):return current['job']
        def public(self,j):return j
        async def start(self,bvid,kind,scope,cid):
            calls.append((bvid,kind,scope,cid));current['job']={'id':'test-job','bvid':bvid,'kind':kind,'status':'running','message':'测试采集','responses':1,'received':20,'retry_after':0,'parts':[{'cid':10}],'part_index':0,'segment':1};return current['job']
        async def cancel(self,identity=None):
            if current['job']:current['job']['status']='paused'
        async def resume(self,identity):current['job']['status']='complete';current['job']['message']='接口遍历结束';return current['job']
    app.state.bili_auth=Auth();app.state.full_text=Service()
    client=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')
    def serve(route):
        req=route.request;url=urlsplit(req.url)
        response=client.request(req.method,url.path+('?' + url.query if url.query else ''),content=req.post_data,headers={k:v for k,v in req.headers.items() if k in {'origin','content-type','sec-fetch-site'}})
        route.fulfill(status=response.status_code,headers={k:v for k,v in response.headers.items() if k.lower() not in {'content-length','content-encoding'}},body=response.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1280,'height':1000});page.route('**/*',serve)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1/settings');page.locator('#bili-qr').click()
            expect(page.locator('#bili-auth-status')).to_contain_text('测试账户')
            assert page.locator('#bili-qr-image').is_hidden()
            page.locator('#bili-logout').click();expect(page.locator('#bili-auth-status')).to_contain_text('尚未登录')
            page.goto(f'http://127.0.0.1/videos/{BV}')
            page.locator('#full-text-control summary').click()
            page.locator('#full-text-form button').click()
            expect(page.locator('#full-text-progress')).to_contain_text('累计读取 20 条')
            assert calls==[(BV,'danmaku','selected',10)]
            page.locator('#full-text-pause').click();expect(page.locator('#full-text-resume')).to_be_visible()
            page.locator('#full-text-resume').click();expect(page.locator('#full-text-progress')).to_contain_text('接口遍历结束')
            assert not errors
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        finally:browser.close()
