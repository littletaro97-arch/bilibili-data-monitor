import asyncio,os,socket,threading,time
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from app.database import Database,Repository
from app.models import VideoInfo,VideoStats
from app.main import create_app

@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in browser')
def test_slow_submit_keeps_content_loader_anchor_and_narrow_layout(tmp_path,monkeypatch):
 import uvicorn
 from playwright.sync_api import sync_playwright,expect
 db=Database(tmp_path/'ui.db');db.initialize();repo=Repository(db)
 ids=[]
 for n in range(24):
  bv=f'BV{n:010d}';repo.upsert_video(VideoInfo(bv,title='布局验收 '+str(n),pubdate=1791345600));ids.append(repo.create_task(bv,300,60,100))
 repo.insert_snapshot(VideoStats('BV0000000000',view_count=100))
 app=create_app();app.state.repository=repo
 async def collect(*args,**kwargs):await asyncio.sleep(1.3);return True
 app.state.crawl_service.collect_once=collect
 sock=socket.socket();sock.bind(('127.0.0.1',0));base=f'http://127.0.0.1:{sock.getsockname()[1]}'
 server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='off'));thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
 deadline=time.monotonic()+5
 while not server.started and time.monotonic()<deadline:time.sleep(.02)
 assert server.started
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True)
  try:
   page=browser.new_page(viewport={'width':1400,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(base+'/');expect(page.locator('.message.warning')).to_contain_text('数量提醒阈值')
   card=page.locator('.task-card').nth(12);card.scroll_into_view_if_needed();page.wait_for_timeout(200)
   url=card.get_attribute('data-detail-url');old_top=card.bounding_box()['y']
   button=card.get_by_role('button',name='立即采集',exact=True)
   page.evaluate("""document.addEventListener('submit',e=>{const button=e.submitter;setTimeout(()=>sessionStorage.setItem('loading-test',JSON.stringify({busy:button.getAttribute('aria-busy'),opacity:Number(getComputedStyle(document.querySelector('main')).opacity),marks:button.querySelectorAll('.loading-mark').length})),50);setTimeout(()=>scrollBy(0,20),150);},{once:true});""")
   with page.expect_navigation(wait_until='load'):button.click()
   state=page.evaluate("JSON.parse(sessionStorage.getItem('loading-test'))")
   assert state['busy']=='true' and state['opacity']>.9 and state['marks']==1
   old_top-=20  # Preserve the user's scroll during the slow request as well.
   restored=page.locator(f'[data-detail-url="{url}"]')
   page.wait_for_function('(arg)=>Math.abs(document.querySelector(`[data-detail-url="${arg.url}"]`).getBoundingClientRect().top-arg.top)<4',arg={'url':url,'top':old_top})
   assert page.evaluate('scrollY')>0
   page.reload()
   page.wait_for_function('(arg)=>Math.abs(document.querySelector(`[data-detail-url="${arg.url}"]`).getBoundingClientRect().top-arg.top)<4',arg={'url':url,'top':old_top})
   page.set_viewport_size({'width':980,'height':1500});page.goto(base+'/videos/BV0000000000')
   expect(page.locator('#floating-nav')).to_be_visible()
   assert page.locator('main').evaluate('e=>getComputedStyle(e).paddingRight')=='24px'
   assert page.locator('.video-metadata .metric').first.bounding_box()['width']>200
   time_tile=page.locator('.metric-time').bounding_box();source=page.locator('[data-latest-field=source_type]').locator('..').bounding_box()
   assert abs(time_tile['y']-source['y'])<2
   close=page.get_by_role('button',name='暂时隐藏目录');close.click();expect(page.locator('#floating-nav')).to_be_hidden()
   page.reload();expect(page.locator('#floating-nav')).to_be_hidden()
   assert page.evaluate("JSON.parse(localStorage.getItem('bilibili-detail-navigation')||'{}').enabled!==false")
   page.goto(base+'/settings');page.goto(base+'/videos/BV0000000000');expect(page.locator('#floating-nav')).to_be_visible()
   page.locator('.video-overview').screenshot(path=str(tmp_path/'portrait-overview.png'))
   page.locator('#latest-data').screenshot(path=str(tmp_path/'portrait-latest.png'))
   assert not errors
  finally:browser.close();server.should_exit=True;thread.join(timeout=5);sock.close()
