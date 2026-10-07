import asyncio
from unittest.mock import AsyncMock,Mock
import pytest
from app.database import Database,Repository,local_now,parse_iso
from app.models import VideoInfo,VideoStats,RiskControlError,LoginRequiredError
from app.services.video_service import VideoService
from app.services.up_monitor_service import UpMonitorService

BV1='BV1xx411c7mD';BV2='BV1yy411c7mD';BV3='BV1zz411c7mD'

def row(bvid,stamp):return {'bvid':bvid,'pubdate':stamp,'title':bvid,'author':'测试UP'}

def setup(tmp_path,limit=10):
 db=Database(tmp_path/'up.db');db.initialize();repo=Repository(db)
 provider=AsyncMock();provider.fetch_video_info.side_effect=lambda bvid:VideoInfo(bvid,title=bvid,owner_mid=123)
 videos=VideoService(repo,provider,60,300,limit)
 space=AsyncMock();space.page.return_value=([row(BV1,100)],1)
 crawl=AsyncMock();service=UpMonitorService(repo,space,videos,crawl,3600,300)
 return service,repo,space,crawl

@pytest.mark.asyncio
async def test_first_baseline_pinned_old_multiple_new_and_restart(tmp_path):
 service,repo,space,crawl=setup(tmp_path)
 identity=await service.add('123',300,60)
 assert not repo.list_tasks()
 space.page.return_value=([row(BV1,100),row(BV2,120),row(BV3,120)],3)
 await service.poll(identity)
 assert {t['bvid'] for t in repo.list_tasks()}=={BV2,BV3}
 assert crawl.collect_once.await_count==2
 assert all(c.kwargs['collection_source']=='UP_MONITOR' for c in crawl.collect_once.await_args_list)
 replacement=UpMonitorService(repo,space,service.video_service,crawl)
 await replacement.poll(identity)
 assert len(repo.list_tasks())==2 and crawl.collect_once.await_count==2
 regular,groups=service.layout(repo.list_tasks());assert not regular and len(groups[0]['tasks'])==2
 service.store.promote(identity,BV2)
 assert [t['bvid'] for t in service.layout(repo.list_tasks())[0]]==[BV2]

@pytest.mark.asyncio
async def test_auto_up_tasks_exceed_threshold_without_displacing_manual_tasks(tmp_path):
 service,repo,space,crawl=setup(tmp_path,limit=1)
 identity=await service.add('123',300,60)
 repo.upsert_video(VideoInfo(BV3));manual=repo.create_task(BV3,300,60,1)
 space.page.return_value=([row(BV2,120)],1)
 await service.poll(identity)
 assert not service.store.pending(identity) and repo.count_active_tasks()==2
 assert repo.get_task_by_bvid(BV2)['automatic']==1
 assert repo.count_active_tasks(manual_only=True)==1
 assert repo.get_task(manual)['status']=='running'
 service.store.state(identity,'paused');await service.poll(identity)
 repo.set_task_status(manual,'paused')
 service.store.state(identity,'running')
 with repo.database.connect() as c:c.execute('UPDATE up_monitors SET cooldown_until=NULL WHERE id=?',(identity,))
 space.page.return_value=([row(BV1,100)],1)
 await service.poll(identity)
 assert repo.get_task_by_bvid(BV2) and not service.store.pending(identity)

@pytest.mark.asyncio
async def test_login_expiry_pauses_all_risk_cools_all_no_retry(tmp_path):
 service,repo,space,crawl=setup(tmp_path)
 a=await service.add('123',300,60);b=await service.add('456',300,60)
 space.page.side_effect=LoginRequiredError('登录失效')
 await service.poll(a)
 assert all(m['status']=='needs_login' for m in service.store.list())
 service.store.state(a,'running');service.store.state(b,'running');space.page.reset_mock();space.page.side_effect=RiskControlError('限制')
 await service.poll(a);await service.poll(b)
 assert space.page.await_count==1
 assert all(parse_iso(m['cooldown_until'])>local_now() for m in service.store.list())

@pytest.mark.asyncio
async def test_pause_during_metadata_fetch_never_creates_task(tmp_path):
 service,repo,space,crawl=setup(tmp_path);identity=await service.add('123',300,60)
 space.page.return_value=([row(BV2,120)],1)
 async def info(bvid):
  service.store.state(identity,'paused');return VideoInfo(bvid)
 service.video_service.provider.fetch_video_info.side_effect=info
 await service.poll(identity)
 assert not repo.list_tasks() and service.store.pending(identity)

@pytest.mark.asyncio
async def test_existing_recycled_task_never_revived(tmp_path):
 service,repo,space,crawl=setup(tmp_path);identity=await service.add('123',300,60)
 repo.upsert_video(VideoInfo(BV2));t=repo.create_task(BV2,900,60,10);repo.set_task_status(t,'stopped')
 space.page.return_value=([row(BV2,120)],1);await service.poll(identity)
 assert repo.get_task(t)['status']=='stopped' and repo.get_task(t)['interval_seconds']==900

@pytest.mark.asyncio
async def test_more_than_one_page_and_failure_never_advances_checkpoint(tmp_path):
 service,repo,space,crawl=setup(tmp_path);identity=await service.add('123',300,60)
 space.page.side_effect=[([row(BV2,120)],60),RiskControlError('分页限制')]
 await service.poll(identity)
 assert service.store.get(identity)['baseline_pubdate']==100 and not repo.list_tasks()

@pytest.mark.asyncio
async def test_provider_reuses_login_and_includes_other_owner_collaboration():
 from app.collectors.up_provider import UpVideoProvider
 client=AsyncMock();auth=Mock()
 auth.status.return_value={'saved':True};auth.cookies={'SESSDATA':'synthetic-test-only'}
 auth.validate=AsyncMock(return_value={'wbi_img':{'img_url':'https://i0.hdslb.com/'+('a'*32)+'.png','sub_url':'https://i0.hdslb.com/'+('b'*32)+'.png'}})
 client.authenticated_response.return_value={'data':{'page':{'count':2},'list':{'vlist':[{'bvid':BV1,'created':100,'mid':123,'title':'本人'}, {'bvid':BV2,'created':120,'mid':456,'title':'合作'}]}}}
 rows,total=await UpVideoProvider(client,auth).page(123)
 assert [r['bvid'] for r in rows]==[BV1,BV2] and total==2
 assert rows[1]['owner_mid']==456
 args=client.authenticated_response.call_args.args
 assert args[0]=='https://api.bilibili.com/x/space/wbi/arc/search' and 'w_rid' in args[2]
 auth.validate.assert_awaited_once()


@pytest.mark.asyncio
async def test_collaboration_belongs_to_monitored_up_but_keeps_actual_video_author(tmp_path):
 service,repo,space,crawl=setup(tmp_path)
 initial=row(BV1,100);initial['owner_mid']=123
 space.page.return_value=([initial],1);identity=await service.add('123',300,60)
 collaboration=row(BV2,120);collaboration['owner_mid']=456
 space.page.return_value=([initial,collaboration],2)
 service.video_service.provider.fetch_video_info.side_effect=lambda bvid:VideoInfo(bvid,title='合作新稿',owner_mid=456,owner_name='主投稿作者')
 await service.poll(identity)
 assert repo.get_task_by_bvid(BV2)
 assert repo.get_video(BV2)['owner_mid']==456
 regular,groups=service.layout(repo.list_tasks());assert not regular and groups[0]['tasks'][0]['bvid']==BV2
