import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
import pytest
from app.collectors.bilibili_client import BilibiliClient
from app.models import CommentUnavailableError, ProviderError, RiskControlError
from app.services.full_text_service import FullTextService
from tests.test_full_text import setup, BV, root

@pytest.mark.asyncio
async def test_unavailable_root_keeps_original_and_continues(tmp_path):
    repo,s,a,p=setup(tmp_path)
    p.roots=AsyncMock(return_value={'replies':[root('gone',3),root('good',1)],'cursor':{'is_end':True}})
    p.children=AsyncMock(side_effect=[CommentUnavailableError('missing'),
        {'page':{'num':1,'size':20,'count':1},'replies':[root('child',parent='good')]}])
    job=await s.start(BV,'comments','all',0);await s.task
    saved=s.load(job['id'])
    assert saved['status']=='complete' and saved['state']['unavailable_roots']==1
    rows={r['rpid']:r for r in repo.list_comments(BV)}
    assert rows['gone']['message']=='文本gone' and rows['gone']['visibility']=='unavailable'
    assert rows['good']['visibility']=='observed' and rows['child']['parent_rpid']=='good'
    assert [call.args[1] for call in p.children.call_args_list]==['gone','good']
    p.roots.return_value={'replies':[root('gone')],'cursor':{'is_end':True}}
    await s.start(BV,'comments','all',0);await s.task
    assert next(r for r in repo.list_comments(BV) if r['rpid']=='gone')['visibility']=='observed'

@pytest.mark.asyncio
@pytest.mark.parametrize('error',[ProviderError('bad shape'),RiskControlError('restricted')])
async def test_other_child_errors_keep_checkpoint(tmp_path,error):
    repo,s,a,p=setup(tmp_path)
    p.roots=AsyncMock(return_value={'replies':[root('1',3)],'cursor':{'is_end':True}})
    p.children=AsyncMock(side_effect=error)
    job=await s.start(BV,'comments','all',0);await s.task
    saved=s.load(job['id'])
    assert saved['status']=='paused' and saved['state']['pending']['index']==0
    assert not s.root_done(job['id'],'1') and repo.list_comments(BV)[0]['visibility']=='observed'

@pytest.mark.asyncio
@pytest.mark.parametrize('path,typed',[('/x/v2/reply/reply',True),('/x/v2/reply/wbi/main',False)])
async def test_missing_classification_is_endpoint_specific(monkeypatch,path,typed):
    actual=httpx.AsyncClient
    transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'code':12006,'message':'没有该评论','data':None}))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(transport=transport,**kw))
    with pytest.raises(ProviderError) as caught:
        await BilibiliClient().authenticated_response('https://api.bilibili.com'+path,{})
    assert isinstance(caught.value,CommentUnavailableError) is typed

@pytest.mark.asyncio
async def test_manual_queue_preserves_active_job_and_batch_limit(tmp_path):
    repo,s,a,p=setup(tmp_path,budget=1)
    entered=asyncio.Event();release=asyncio.Event()
    async def segment(*args):entered.set();await release.wait();return []
    p.segment=segment
    current=await s.start(BV,'danmaku','selected',10);await entered.wait()
    p.roots=AsyncMock(return_value={'replies':[root('1',1)],'cursor':{'is_end':True}})
    p.children=AsyncMock(return_value={'page':{'num':1,'size':20,'count':1},'replies':[root('child',parent='1')]})
    queued=await s.start(BV,'comments','all',0)
    assert queued['status']=='queued' and s.active==current['id']
    task=repo.create_task(BV,60,60,10)
    await s.enqueue_tick(BV)
    assert not s.load(queued['id'])['state'].get('automatic')
    repo.set_task_status(task,'paused')
    assert (await s.resume(current['id']))['status']=='running'
    assert (await s.resume(queued['id']))['status']=='queued'
    with pytest.raises(ProviderError,match='同类'):await s.start(BV,'comments','all',0)
    release.set();await s.task
    await s.pump();await s.task
    saved=s.load(queued['id'])
    assert saved['status']=='paused' and saved['state']['pending']['index']==0
    assert not saved['state'].get('queued_manual')
    await s.pump()
    assert p.roots.await_count==1 and p.children.await_count==0
    await s.resume(queued['id']);await s.task
    assert s.load(queued['id'])['status']=='complete'

@pytest.mark.asyncio
async def test_queued_resume_can_cancel_without_losing_checkpoint(tmp_path):
    repo,s,a,p=setup(tmp_path,budget=1)
    p.roots=AsyncMock(return_value={'replies':[root('1',1)],'cursor':{'is_end':True}})
    p.children=AsyncMock()
    paused=await s.start(BV,'comments','all',0);await s.task
    checkpoint=s.load(paused['id'])['state']['pending']
    entered=asyncio.Event()
    async def segment(*args):entered.set();await asyncio.Event().wait()
    p.segment=segment
    running=await s.start(BV,'danmaku','selected',10);await entered.wait()
    assert (await s.resume(paused['id']))['status']=='queued'
    assert s.active==running['id']
    await s.cancel(paused['id'])
    assert s.load(paused['id'])['state']['pending']==checkpoint
    await s.cancel(running['id']);await s.pump()
    assert p.children.await_count==0

@pytest.mark.asyncio
async def test_queued_manual_rechecks_account_before_fetching(tmp_path):
    repo,s,a,p=setup(tmp_path)
    entered=asyncio.Event();release=asyncio.Event()
    async def segment(*args):entered.set();await release.wait();return []
    p.segment=segment
    await s.start(BV,'danmaku','selected',10);await entered.wait()
    p.roots=AsyncMock(return_value={'replies':[],'cursor':{'is_end':True}})
    queued=await s.start(BV,'comments','all',0)
    release.set();await s.task;a.account='different'
    await s.pump();await s.task
    assert s.load(queued['id'])['state']['failure_kind']=='account' and p.roots.await_count==0

@pytest.mark.asyncio
@pytest.mark.parametrize('manual_pause',[False,True])
async def test_legacy_recovery_respects_manual_pause(tmp_path,manual_pause):
    repo,s,a,p=setup(tmp_path,budget=1)
    p.roots=AsyncMock(return_value={'replies':[root('1',1)],'cursor':{'is_end':True}})
    job=await s.start(BV,'comments','all',0);await s.task
    saved=s.load(job['id']);saved['message']='平台接口失败：code=12006；任务未完成'
    saved['state'].update(automatic=True,manual_pause=manual_pause,failure_kind='provider');s.save(saved)
    recovered=FullTextService(repo,p,a).load(job['id'])
    assert recovered['status']==('paused' if manual_pause else 'queued')
    assert recovered['state']['pending']==saved['state']['pending']

@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in browser')
def test_operation_failure_keeps_polling():
    from playwright.sync_api import sync_playwright,expect
    from jinja2 import Environment
    template=(Path(__file__).parents[1]/'app/reports/templates/full_text_controls.html').read_text(encoding='utf-8')
    html=Environment().from_string(template).render(video={'bvid':BV},task=None)
    calls=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page();page.clock.install()
            def serve(route):
                if route.request.method=='POST':route.fulfill(status=400,json={'error':'模拟操作失败'})
                else:calls.append(1);route.fulfill(json={'job':None,'jobs':[]})
            page.route('**/api/text/jobs/**',serve)
            page.route('http://local.test/',lambda route:route.fulfill(body='<select id="text-part"><option value="10">P1</option></select>'+html,content_type='text/html'))
            page.goto('http://local.test/')
            page.locator('#full-text-control').evaluate('(el)=>el.open=true')
            page.locator('#full-text-form button').click()
            expect(page.locator('#full-text-progress')).to_contain_text('模拟操作失败')
            before=len(calls)
            with page.expect_response('**/api/text/jobs/'+BV):page.clock.fast_forward(3100)
            assert len(calls)>before
        finally:browser.close()
