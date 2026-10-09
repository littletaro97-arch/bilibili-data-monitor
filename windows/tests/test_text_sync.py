import asyncio
import time
from unittest.mock import AsyncMock
import pytest
from app.models import RequestFailure,RiskControlError,LoginRequiredError,DanmakuItem,VideoComment,VideoStats
from app.services.network_retry import network_retry_delay
from app.services.crawl_service import CrawlService
from tests.test_full_text import setup,BV,root


def active(repo):
    return repo.create_task(BV,60,60,10)


@pytest.mark.asyncio
async def test_statistics_enqueue_without_waiting_for_body(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo)
    provider=AsyncMock();provider.fetch_video_stats.return_value=VideoStats(BV,view_count=100)
    crawl=CrawlService(repo,provider,1,600,1800,0);crawl.full_text=s
    assert await crawl.collect_once(BV)
    assert repo.latest_snapshot(BV)['view_count']==100
    assert len(s.jobs(BV))==2 and p.view.await_count==0
    await s.enqueue_tick(BV)
    assert len(s.jobs(BV))==2


@pytest.mark.asyncio
async def test_overlapping_ticks_continue_cursor_and_rotate_channels(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo)
    calls=[]
    async def roots(aid,offset):
        calls.append(offset);i=len(calls)
        return {'replies':[root(str(i))],'cursor':{'is_end':False,'pagination_reply':{'next_offset':str(i)}}}
    p.roots=roots
    await s.enqueue_tick(BV);identity=s.latest_kind(BV,'comments')['id']
    await s.pump();await s.task
    assert calls==['','1','2','3']
    await s.enqueue_tick(BV);assert s.latest_kind(BV,'comments')['id']==identity
    await s.pump();await s.task
    assert p.segment.await_count==2
    await s.pump();await s.task
    assert calls[-4:]==['4','5','6','7'] and s.load(identity)['state']['saved_new']==8


@pytest.mark.asyncio
async def test_network_backoff_survives_restart_without_risk_cooldown(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo);p.roots=AsyncMock(side_effect=RequestFailure('timeout','timeout'))
    await s.enqueue_tick(BV)
    dm=s.latest_kind(BV,'danmaku');dm['state']['manual_pause']=True;s.save(dm)
    expected=[5,10,20,40,80,160,320,600,600]
    for delay in expected:
        await s.pump();await s.task
        job=s.latest_kind(BV,'comments');assert job['status']=='retry_wait'
        assert delay-1<=job['state']['retry_at']-time.time()<=delay
        s.check_cooldown()  # network waits are never shared platform cooldown
        before=p.roots.await_count;await s.pump();assert p.roots.await_count==before
        job['state']['retry_at']=0;s.save(job)
    from app.services.full_text_service import FullTextService
    restored=FullTextService(repo,p,a);assert restored.load(job['id'])['state']['network_failures']==9
    p.roots.side_effect=None;p.roots.return_value={'replies':[root('new')],'cursor':{'is_end':True}}
    await restored.pump();await restored.task
    assert restored.load(job['id'])['status']=='complete'
    assert restored.load(job['id'])['state']['network_failures']==0


@pytest.mark.asyncio
async def test_risk_blocks_shared_text_channel_but_login_does_not_retry(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo);p.roots=AsyncMock(side_effect=RiskControlError('secret'))
    await s.enqueue_tick(BV);await s.pump();await s.task
    job=s.latest_kind(BV,'comments');assert job['state']['failure_kind']=='risk'
    await s.pump();assert p.segment.await_count==0
    assert 'secret' not in job['message']
    with repo.database.connect() as c:c.execute('DELETE FROM text_job_control')
    job['state']['retry_at']=0;s.save(job)
    p.roots.side_effect=LoginRequiredError('secret');await s.pump();await s.task
    job=s.latest_kind(BV,'danmaku')
    # whichever fair channel runs first, then exhaust the queued comments explicitly
    await s.pump()
    if s.task:await s.task
    assert s.latest_kind(BV,'comments')['status']=='waiting_login'


@pytest.mark.asyncio
async def test_pause_recycle_account_and_manual_stop_are_preserved(tmp_path):
    repo,s,a,p=setup(tmp_path);identity=active(repo);await s.enqueue_tick(BV)
    repo.set_task_status(identity,'paused');await s.pump();assert s.task is None
    repo.set_task_status(identity,'running');job=s.latest_kind(BV,'comments');await s.cancel(job['id'])
    await s.enqueue_tick(BV);assert s.load(job['id'])['state']['manual_pause']
    repo.set_task_status(identity,'stopped');await s.pump();assert s.task is None


@pytest.mark.asyncio
async def test_real_ids_are_distinct_and_old_or_removed_text_is_retained(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo)
    repo.insert_comments([VideoComment(BV,'1',message='old')])
    p.roots=AsyncMock(return_value={'replies':[root('1'),root('2'),root('2')],'cursor':{'is_end':True}})
    await s.enqueue_tick(BV);await s.pump();await s.task
    job=s.latest_kind(BV,'comments')
    assert job['state']['received']==3 and job['state']['saved_new']==1
    assert len(repo.list_comments(BV))==2
    p.roots.return_value={'replies':[],'cursor':{'is_end':True}}
    await s.enqueue_tick(BV);await s.pump();await s.task
    await s.pump();await s.task
    assert len(repo.list_comments(BV))==2


@pytest.mark.asyncio
async def test_transport_failure_stats_uses_backoff_and_recovers(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo)
    provider=AsyncMock();provider.fetch_video_stats.side_effect=RequestFailure('network','network')
    crawl=CrawlService(repo,provider,1,600,1800,0)
    for i in range(1,5):
        task=repo.get_task_by_bvid(BV)
        with repo.database.connect() as c:c.execute('UPDATE crawl_tasks SET cooldown_until=NULL')
        with pytest.raises(RequestFailure):await crawl.collect_once(BV)
        from app.database import parse_iso,local_now
        latest=repo.get_task_by_bvid(BV);delay=(parse_iso(latest['cooldown_until'])-local_now()).total_seconds()
        assert network_retry_delay(i)-1<=delay<=network_retry_delay(i) and latest['status']=='running'


@pytest.mark.asyncio
async def test_video_pause_inflight_then_resume_uses_same_job(tmp_path):
    repo,s,a,p=setup(tmp_path);task=active(repo);entered=asyncio.Event()
    async def blocked(*args):entered.set();await asyncio.Event().wait()
    p.roots=blocked
    await s.enqueue_tick(BV);await s.pump();await entered.wait()
    job=s.latest_kind(BV,'comments');identity=job['id']
    await s.enqueue_tick(BV)
    assert s.latest_kind(BV,'comments')['id']==identity
    repo.set_task_status(task,'paused');await s.cancel_video(BV)
    assert not s.load(identity)['state'].get('manual_pause')
    await s.pump();assert p.segment.await_count==0
    repo.set_task_status(task,'running');p.roots=AsyncMock(return_value={'replies':[],'cursor':{'is_end':True}})
    await s.enqueue_tick(BV)
    for _ in range(2):await s.pump();await s.task
    assert s.load(identity)['status']=='complete'


@pytest.mark.asyncio
async def test_logged_out_queue_has_no_platform_calls(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo);a.cookies={}
    await s.enqueue_tick(BV);await s.pump()
    assert p.view.await_count==0 and a.validate.await_count==0 and s.task is None
    a.cookies={'SESSDATA':'test-secret'};p.roots=AsyncMock(return_value={'replies':[],'cursor':{'is_end':True}})
    await s.pump();await s.task
    assert s.latest_kind(BV,'comments')['status']=='complete'


@pytest.mark.asyncio
async def test_statistics_tick_does_not_wait_for_login_control_lock(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo)
    async with s.lock:
        await asyncio.wait_for(s.enqueue_tick(BV),timeout=.2)
        assert not s.jobs(BV)
        with repo.database.connect() as c:assert c.execute("SELECT 1 FROM text_job_control WHERE key=?",('tick:'+BV,)).fetchone()
    p.roots=AsyncMock(return_value={'replies':[],'cursor':{'is_end':True}})
    await s.pump();await s.task
    assert len(s.jobs(BV))==2
    with repo.database.connect() as c:assert not c.execute("SELECT 1 FROM text_job_control WHERE key=?",('tick:'+BV,)).fetchone()


@pytest.mark.asyncio
async def test_deferred_tick_is_discarded_after_video_pauses(tmp_path):
    repo,s,a,p=setup(tmp_path);identity=active(repo)
    async with s.lock:await s.enqueue_tick(BV)
    repo.set_task_status(identity,'paused')
    await s.pump()
    assert not s.jobs(BV) and s.task is None
    with repo.database.connect() as c:assert not c.execute("SELECT 1 FROM text_job_control WHERE key=?",('tick:'+BV,)).fetchone()


@pytest.mark.asyncio
async def test_new_logged_out_job_can_resume_after_login(tmp_path):
    repo,s,a,p=setup(tmp_path);active(repo);a.cookies={}
    await s.enqueue_tick(BV);identity=s.latest_kind(BV,'comments')['id']
    a.cookies={'SESSDATA':'test-secret'}
    p.roots=AsyncMock(return_value={'replies':[],'cursor':{'is_end':True}})
    await s.resume(identity);await s.task
    assert s.load(identity)['status']=='complete'


@pytest.mark.asyncio
@pytest.mark.parametrize('page',[1,2])
async def test_explicit_page_limits_auto_and_manual_danmaku_only(tmp_path,page):
    from app.services.video_service import VideoService
    repo,s,a,p=setup(tmp_path)
    metadata=AsyncMock()
    from app.models import VideoInfo
    metadata.fetch_video_info.return_value=VideoInfo(BV,aid=123,cid=10)
    video=VideoService(repo,metadata,60,300,10)
    await video.add_video_task(f'https://www.bilibili.com/video/{BV}/?p={page}',60)
    assert repo.get_task_by_bvid(BV)['selected_page']==page
    from app.ui.pages import templates
    controls=templates.get_template('full_text_controls.html').render(video={'bvid':BV},task=dict(repo.get_task_by_bvid(BV)))
    assert f'仅任务 P{page}' in controls and '<option value="all">' not in controls
    p.view.return_value=(123,[{'cid':10,'page':1,'duration':1,'name':'P1'},{'cid':11,'page':2,'duration':1,'name':'P2'}])
    p.roots=AsyncMock(return_value={'replies':[],'cursor':{'is_end':True}})
    await s.enqueue_tick(BV)
    await s.pump();await s.task
    await s.pump();await s.task
    assert p.segment.await_count==1 and p.segment.call_args.args==(BV,9+page,1)
    assert s.latest_kind(BV,'comments')['state']['total_parts']==2
    await s.start(BV,'danmaku','all',10);await s.task
    assert p.segment.await_count==2 and p.segment.call_args.args==(BV,9+page,1)
    identity=repo.get_task_by_bvid(BV)['id'];repo.set_task_status(identity,'stopped');video.restore_task(identity)
    assert repo.get_task_by_bvid(BV)['selected_page']==page


def test_metadata_compatibility_retry_is_once_and_keeps_checkpoint(tmp_path):
    import json
    from app.services.full_text_service import FullTextService
    repo,s,a,p=setup(tmp_path);active(repo)
    job={'id':'metadata-old','bvid':BV,'kind':'danmaku','status':'paused','message':'弹幕分段缺少可识别字段，进度未推进',
         'state':{'automatic':True,'failure_kind':'provider','part_index':1,'segment':1,'received':194}}
    s.save(job)
    restored=FullTextService(repo,p,a);current=restored.load(job['id'])
    assert current['status']=='queued' and current['state']['part_index']==1 and current['state']['received']==194
    current['status']='paused';current['message']=job['message'];current['state']['failure_kind']='provider';restored.save(current)
    again=FullTextService(repo,p,a)
    assert again.load(job['id'])['status']=='paused'
    current['id']='manual';current['state']['manual_pause']=True;current['state'].pop('metadata_compat_retry');again.save(current)
    assert FullTextService(repo,p,a).load('manual')['status']=='paused'
