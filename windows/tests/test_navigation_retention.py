import os
from urllib.parse import urlsplit
import pytest
from fastapi.testclient import TestClient
from app.database import Database,Repository
from app.models import VideoInfo,VideoComment,DanmakuItem

BV='BV1xx411c7mD'

def repo_at(tmp_path):
    db=Database(tmp_path/'test.db');db.initialize();repo=Repository(db)
    repo.upsert_video(VideoInfo(BV,title='导航测试视频',cid=10,aid=123))
    return repo

def test_missing_text_and_tombstone_never_remove_capture(tmp_path):
    repo=repo_at(tmp_path)
    repo.insert_comments([VideoComment(BV,'one',message='旧评论'),VideoComment(BV,'two',message='被删除但已采集')])
    repo.insert_danmaku([DanmakuItem(BV,10,1,'弹幕原文',100,source_id='one')])
    repo.insert_comments([VideoComment(BV,'one',message='编辑后的评论')])
    repo.insert_comments([VideoComment(BV,'one',message='[已删除]')])
    repo.insert_danmaku([])
    rows={r['rpid']:r['message'] for r in repo.list_comments(BV)}
    assert rows=={'one':'编辑后的评论','two':'被删除但已采集'}
    assert repo.list_danmaku(BV)[0]['text']=='弹幕原文'
    with repo.database.connect() as c:
        assert {r['message'] for r in c.execute('SELECT message FROM comment_text_history')}=={'旧评论','编辑后的评论'}
    from app.services.export_service import ExportService
    exported=ExportService(repo,tmp_path/'exports').export_all()
    assert '旧评论' in (exported/'comment_text_history.csv').read_text(encoding='utf-8-sig')

@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in headless browser')
def test_task_clicks_floating_directory_and_settings(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    from app.main import create_app
    from app.services.video_service import VideoService
    from app.collectors.provider import MockVideoDataProvider
    repo=repo_at(tmp_path);task_id=repo.create_task(BV,300,60,10)
    app=create_app();app.state.repository=repo
    app.state.video_service=VideoService(repo,MockVideoDataProvider(),60,300,10)
    client=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')
    posts=[]
    def serve(route):
        req=route.request;url=urlsplit(req.url)
        if url.netloc!='127.0.0.1':route.fulfill(status=200,body='external video');return
        if req.method=='POST' and url.path.startswith('/tasks/'):
            posts.append(url.path);route.fulfill(status=200,body='action');return
        result=client.request(req.method,url.path,content=req.post_data)
        route.fulfill(status=result.status_code,headers={k:v for k,v in result.headers.items() if k.lower() not in {'content-length','content-encoding'}},body=result.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1920,'height':1080});page.route('**/*',serve)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1/')
            with page.expect_popup() as popup:page.locator('.task-title').click()
            assert popup.value.url.startswith('https://www.bilibili.com/video/'+BV)
            assert page.url=='http://127.0.0.1/'
            popup.value.close()
            for action in ['collect','pause','stop']:
                page.goto('http://127.0.0.1/');page.locator(f'form[action="/tasks/{task_id}/{action}"] button').click()
                assert posts[-1]==f'/tasks/{task_id}/{action}' and '/videos/' not in page.url
            page.goto('http://127.0.0.1/');page.locator('.task-stats').click()
            expect(page).to_have_url(f'http://127.0.0.1/videos/{BV}')
            nav=page.locator('#floating-nav');expect(nav).to_be_visible()
            assert nav.get_attribute('data-side')=='right'
            nav.get_by_role('link',name='04 历史导入').click()
            assert page.locator('[data-chart-panel="history-import"]').evaluate('e=>e.open')
            page.goto('http://127.0.0.1/settings');page.locator('#navigation-side').select_option('left')
            page.goto(f'http://127.0.0.1/videos/{BV}');assert page.locator('#floating-nav').get_attribute('data-side')=='left'
            page.set_viewport_size({'width':900,'height':800});expect(page.locator('#floating-nav-menu')).to_be_visible()
            assert page.locator('.floating-nav-toggle').count()==0
            nav.get_by_role('link',name='01 视频概况').click();expect(page.locator('#floating-nav-menu')).to_be_visible()
            page.goto('http://127.0.0.1/settings');page.locator('#navigation-enabled').uncheck()
            page.goto(f'http://127.0.0.1/videos/{BV}');expect(page.locator('#floating-nav')).to_be_hidden()
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            assert not errors
        finally:browser.close()


@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in headless browser')
def test_card_navigation_restores_preferences_once_with_page_fade(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    from app.main import create_app
    repo=repo_at(tmp_path);repo.create_task(BV,300,60,10)
    app=create_app();app.state.repository=repo
    client=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')
    documents=[]
    def serve(route):
        req=route.request;url=urlsplit(req.url)
        if req.resource_type=='document':documents.append(url.path+'?'+url.query)
        result=client.get(url.path+('?' + url.query if url.query else ''))
        route.fulfill(status=result.status_code,headers={k:v for k,v in result.headers.items() if k.lower() not in {'content-length','content-encoding'}},body=result.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page();page.route('**/*',serve)
            page.add_init_script('''
              window.mainFrames=[];
              const animate=Element.prototype.animate;
              Element.prototype.animate=function(frames,options){
                if(this.tagName==='MAIN')window.mainFrames.push(frames);
                return animate.call(this,frames,options);
              };
            ''')
            for keyboard in [False,True]:
                page.goto('http://127.0.0.1/')
                page.evaluate('(bv)=>localStorage.setItem(`blla:/videos/${bv}:select:left_metric`,"like_count")',BV)
                documents.clear()
                if keyboard:
                    page.locator('.task-card').focus();page.keyboard.press('Enter')
                else:page.locator('.task-stats').click()
                expect(page).to_have_url(f'http://127.0.0.1/videos/{BV}?left_metric=like_count')
                page.wait_for_load_state('load')
                assert documents==[f'/videos/{BV}?left_metric=like_count']
                assert page.evaluate('mainFrames.some(frames=>frames[0].opacity===0 && frames[1].opacity===1 && frames[0].transform==="translateY(4px)")')
            page.locator('nav a[href="/settings"]').click()
            page.wait_for_url('**/settings');page.wait_for_load_state('load')
            assert page.evaluate('mainFrames.some(frames=>frames[0].opacity===0 && frames[1].opacity===1)')
            page.go_back();page.wait_for_load_state('load')
            page.wait_for_function('document.querySelector("main").getAnimations().length===0')
            assert page.locator('main').evaluate('e=>getComputedStyle(e).opacity')=='1'
        finally:browser.close()
