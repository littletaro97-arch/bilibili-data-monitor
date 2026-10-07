import os,socket,threading,time
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from app.database import Database,Repository
from app.models import VideoInfo
from app.main import create_app
from app.services.video_service import VideoService
from app.services.up_monitor_service import UpMonitorService
from app.services.report_service import ReportService

BV1='BV1xx411c7mD';BV2='BV1yy411c7mD'

@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in browser')
def test_up_home_group_move_modal_motion_and_report_delete(tmp_path,monkeypatch):
 import uvicorn
 from playwright.sync_api import sync_playwright,expect
 db=Database(tmp_path/'ui.db');db.initialize();repo=Repository(db)
 app=create_app();app.state.repository=repo
 info=AsyncMock();info.fetch_video_info.side_effect=lambda bvid:VideoInfo(bvid,title='视频'+bvid,owner_mid=123)
 videos=VideoService(repo,info,60,300,10);crawl=AsyncMock();space=AsyncMock()
 space.page.return_value=([{'bvid':BV1,'title':'旧稿','pubdate':100,'author':'测试UP'}],1)
 service=UpMonitorService(repo,space,videos,crawl)
 app.state.up_monitor=service;app.state.video_service=videos;app.state.crawl_service=crawl
 app.state.report_service=ReportService(repo,tmp_path/'reports',Path(__file__).parents[1]/'app/reports/templates')
 monkeypatch.setattr('app.services.report_service.webbrowser.open',lambda _:True)
 sock=socket.socket();sock.bind(('127.0.0.1',0));base=f'http://127.0.0.1:{sock.getsockname()[1]}'
 server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='off'))
 thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
 deadline=time.monotonic()+5
 while not server.started and time.monotonic()<deadline:time.sleep(.02)
 assert server.started
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True)
  try:
   page=browser.new_page(viewport={'width':1500,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.add_init_script('''window.motionCalls=[];const animate=Element.prototype.animate;Element.prototype.animate=function(frames,options){motionCalls.push({tag:this.tagName,options});return animate.call(this,frames,options);};''')
   page.goto(base+'/');page.locator('#up-input').fill('123');page.locator('#up-video-interval').fill('60')
   page.get_by_role('button',name='添加 UP',exact=True).click();expect(page.locator('.up-monitor')).to_be_visible()
   assert not repo.list_tasks()
   assert page.locator('#up-monitors').evaluate('e=>e.previousElementSibling.querySelector("h2").textContent')=='任务列表'
   assert page.locator('#up-monitors').evaluate('e=>e.nextElementSibling.querySelector("h2").textContent')=='其它设备访问'
   space.page.return_value=([{'bvid':BV2,'title':'新稿','pubdate':120,'author':'测试UP'}],1)
   page.get_by_role('button',name='立即检测',exact=True).click();expect(page.locator('#up-monitors .task-card')).to_have_count(1)
   assert len(repo.list_tasks())==1
   page.get_by_role('button',name='修改采集时间').click();dialog=page.get_by_role('dialog',name='修改采集时间');expect(dialog).to_be_visible()
   assert page.evaluate('motionCalls.some(c=>c.tag==="DIALOG"&&c.options.duration===160)')
   dialog.get_by_role('button',name='取消').click();expect(dialog).not_to_be_visible()
   page.get_by_role('button',name='移至任务列表',exact=True).click();expect(page.locator('#up-monitors .task-card')).to_have_count(0)
   expect(page.locator('.task-card')).to_have_count(1)
   path=app.state.report_service.generate(BV2)
   page.goto(base+'/videos/'+BV2);assert page.locator('form[action$="/phase2/demo"] button').count()==0
   page.locator('[data-chart-panel="reports"]>summary').click()
   page.get_by_role('button',name='删除报告',exact=True).click();confirm=page.get_by_role('dialog',name='确认操作');expect(confirm).to_be_visible()
   confirm.get_by_role('button',name='确定',exact=True).click()
   expect(page.locator('[data-chart-panel="reports"]')).to_have_count(0)
   assert not path.exists() and not errors
   page.clock.install()
   page.goto(base+'/')
   up=service.store.list()[0]
   third='BV1ab411c7mD'
   service.store.discover(up['id'],[{'bvid':third,'title':'后台新稿','pubdate':130}])
   repo.upsert_video(VideoInfo(third,title='后台新稿'));repo.create_task(third,60,60,10);service.store.queued(up['id'],third)
   page.clock.fast_forward(61000)
   expect(page.locator('#up-monitors .task-card')).to_have_count(1)
   page.locator('#up-monitors').screenshot(path=str(tmp_path/'up-monitor-home.png'))
  finally:
   browser.close();server.should_exit=True;thread.join(timeout=5);sock.close()
