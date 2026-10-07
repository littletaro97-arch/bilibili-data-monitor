import pytest
from unittest.mock import AsyncMock
from app.database import Database,Repository
from app.models import AppError,VideoInfo,VideoStats,VideoComment,DanmakuItem
from app.up_monitor_store import UpMonitorStore
from app.services.report_service import ReportService
from pathlib import Path

BV='BV1xx411c7mD'
def make_repo(tmp_path):
 db=Database(tmp_path/'data.db');db.initialize();repo=Repository(db)
 repo.upsert_video(VideoInfo(BV,title='永久删除测试'));identity=repo.create_task(BV,300,60,10)
 return repo,identity

def test_permanent_delete_only_recycled_and_preserves_export_and_up_exclusion(tmp_path):
 repo,identity=make_repo(tmp_path)
 with pytest.raises(AppError):repo.permanently_delete_task(identity)
 repo.insert_snapshot(VideoStats(BV,view_count=1));repo.insert_comments([VideoComment(BV,'a',message='测试')]);repo.insert_danmaku([DanmakuItem(BV,1,1,'测试')])
 report=ReportService(repo,tmp_path/'reports',Path(__file__).parents[1]/'app/reports/templates').generate(BV)
 store=UpMonitorStore(repo);up=store.add(123,'test',[{'bvid':BV,'pubdate':100,'title':'测试'}],300,60);store.queued(up,BV)
 repo.set_task_status(identity,'stopped');repo.permanently_delete_task(identity)
 assert not repo.get_video(BV) and not repo.get_task(identity) and report.exists()
 assert not repo.list_comments(BV) and not repo.list_danmaku(BV) and not repo.list_snapshots(BV)
 store.discover(up,[{'bvid':BV,'pubdate':200,'title':'已删除稿件再次返回'}]);assert not store.pending(up)

@pytest.mark.asyncio
async def test_more_than_300_new_videos_scanned_across_rounds_without_count_limit(tmp_path):
 from app.services.up_monitor_service import UpMonitorService
 from app.services.video_service import VideoService
 repo,_=make_repo(tmp_path);space=AsyncMock();metadata=AsyncMock();metadata.fetch_video_info.side_effect=lambda bv:VideoInfo(bv,title=bv)
 video=VideoService(repo,metadata,60,300,1);crawl=AsyncMock();service=UpMonitorService(repo,space,video,crawl)
 space.page.return_value=([{'bvid':BV,'pubdate':100,'title':'旧稿','author':'test'}],1)
 identity=await service.add('123',300,60)
 all_rows=[{'bvid':f'BV{n:010d}','pubdate':500-n,'title':str(n),'author':'test'} for n in range(350)]
 async def page(mid,pn=1):return all_rows[(pn-1)*30:pn*30],350
 space.page.side_effect=page
 await service.poll(identity)
 assert service.store.get(identity)['scan_page']==10 and service.store.get(identity)['baseline_pubdate']==100
 await service.poll(identity)
 assert service.store.get(identity)['scan_page']==1 and service.store.get(identity)['baseline_pubdate']==500
 with repo.database.connect() as c:assert c.execute("SELECT COUNT(*) FROM up_monitor_videos WHERE monitor_id=? AND state IN ('queued','pending')",(identity,)).fetchone()[0]==350
 assert repo.count_active_tasks()>1 and repo.count_active_tasks(manual_only=True)==1
 assert repo.get_task_by_bvid(all_rows[-1]['bvid']) is not None or service.store.pending(identity)

def test_permanent_delete_endpoint_cancels_capture_and_rejects_remote(tmp_path):
 from fastapi.testclient import TestClient
 from app.main import create_app
 repo,identity=make_repo(tmp_path);app=create_app();app.state.repository=repo
 cancel=AsyncMock();app.state.full_text=type('CaptureStub',(),{'cancel_video':cancel})()
 local=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')
 assert local.post(f'/recycle-bin/{identity}/delete',follow_redirects=False).status_code==303
 assert repo.get_video(BV);cancel.assert_not_awaited()
 repo.set_task_status(identity,'stopped')
 remote=TestClient(app,client=('192.168.1.20',9000),base_url='http://127.0.0.1')
 assert remote.post(f'/recycle-bin/{identity}/delete').status_code==403
 assert local.post(f'/recycle-bin/{identity}/delete',follow_redirects=False).status_code==303
 assert not repo.get_video(BV);cancel.assert_awaited_once_with(BV)

@pytest.mark.asyncio
async def test_unlimited_stored_tasks_dispatch_in_bounded_batches(tmp_path):
 from app.services.crawl_service import CrawlService
 repo,_=make_repo(tmp_path)
 for n in range(11):
  bv=f'BV{n:010d}';repo.upsert_video(VideoInfo(bv));repo.create_task(bv,300,60,None,automatic=True)
 provider=AsyncMock();provider.fetch_video_stats.side_effect=lambda bv:VideoStats(bv,view_count=1)
 service=CrawlService(repo,provider,1,600,3600,0)
 await service.run_due_tasks();assert provider.fetch_video_stats.await_count==4
 assert len(repo.due_running_tasks())==8
 await service.run_due_tasks();assert provider.fetch_video_stats.await_count==8
