from dataclasses import replace
import os
import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def panel(tmp_path,monkeypatch):
    from app.main import create_app
    from app.database import Database,Repository
    from app.models import VideoInfo
    from app.services.report_service import ReportService
    from app.ui import pages
    db=Database(tmp_path/'layout.db');db.initialize();repo=Repository(db)
    repo.upsert_video(VideoInfo('BV1xx411c7mD',title='布局验收视频'))
    app=create_app();app.state.repository=repo
    app.state.browser_opens=[]
    monkeypatch.setattr("app.services.report_service.webbrowser.open",lambda url: app.state.browser_opens.append(url) or True)
    reports=tmp_path/'reports'
    app.state.report_service=ReportService(repo,reports,Path(__file__).parents[1]/'app/reports/templates')
    monkeypatch.setattr(pages,'settings',replace(pages.settings,report=replace(pages.settings.report,output_dir=str(reports))))
    base=pages.load_settings()
    settings=replace(base,database=replace(base.database,path='C:/'+'long_directory/'*30+'database.db'),
                     report=replace(base.report,output_dir='C:/'+'report_directory/'*30))
    monkeypatch.setattr(pages,'load_settings',lambda:settings)
    return TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')


def test_open_report_redirect_and_generation_error(panel,monkeypatch):
    response=panel.post('/videos/BV1xx411c7mD/report',data={'open_report':'true'},follow_redirects=False)
    assert response.status_code==303 and response.headers['location'].startswith('/videos/BV1xx411c7mD?')
    assert panel.app.state.browser_opens[-1].startswith('http://127.0.0.1:')
    report=panel.get('/reports/'+panel.app.state.browser_opens[-1].rsplit('/',1)[-1])
    assert report.status_code==200 and 'text/html' in report.headers['content-type']
    assert '布局验收视频' in report.text
    response=panel.post('/videos/BV1xx411c7mD/report',follow_redirects=False)
    assert response.headers['location'].startswith('/videos/BV1xx411c7mD?')
    def fail(_):raise RuntimeError('test')
    monkeypatch.setattr(panel.app.state.report_service,'generate',fail)
    response=panel.post('/videos/BV1xx411c7mD/report',data={'open_report':'true'},follow_redirects=False)
    assert response.status_code==303 and '/videos/' in response.headers['location'] and 'level=error' in response.headers['location']


@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in headless browser')
def test_layout_bounds_persistent_directory_and_report_button(panel,tmp_path):
    from playwright.sync_api import sync_playwright,expect
    import uvicorn
    # Real local HTTP verifies Chromium's POST -> 303 -> GET redirect chain.
    # Playwright route.fulfill does not re-intercept all redirected requests.
    sock=socket.socket();sock.bind(('127.0.0.1',0))
    base=f'http://127.0.0.1:{sock.getsockname()[1]}'
    server=uvicorn.Server(uvicorn.Config(panel.app,log_level='error',lifespan='off'))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    deadline=time.monotonic()+5
    while not server.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(.01)
    assert server.started
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1280,'height':960})
            page.route('**/api/text/auth',lambda route:route.fulfill(json={'saved':True,'name':'长账户名'*30,'message':'测试状态'}))
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'/settings')
            expect(page.locator('#bili-auth-status')).to_contain_text('测试状态')
            page.wait_for_function('document.querySelector("main").getAnimations().length===0')
            runtime=page.locator('#runtime-settings').bounding_box();account=page.locator('#bili-account').bounding_box()
            assert account['x']>runtime['x']+runtime['width'] and abs(account['y']-runtime['y'])<2
            assert abs(account['height']-runtime['height'])<1
            assert page.locator('.runtime-table code').nth(1).evaluate('e=>e.scrollWidth>e.clientWidth')
            page.locator('.settings-overview').screenshot(path=str(tmp_path/'settings-columns.png'))
            page.locator('[data-theme-toggle]').click()
            page.locator('.settings-overview').screenshot(path=str(tmp_path/'settings-columns-dark.png'))
            for width in [900,390]:
                page.set_viewport_size({'width':width,'height':960})
                runtime=page.locator('#runtime-settings').bounding_box();account=page.locator('#bili-account').bounding_box()
                assert account['y']>runtime['y']+runtime['height']
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            for width in [1280,900,390]:
                page.set_viewport_size({'width':width,'height':960});page.goto(base+'/videos/BV1xx411c7mD')
                expect(page.locator('#floating-nav-menu')).to_be_visible()
                assert page.locator('.floating-nav-toggle').count()==0
                assert page.locator('#floating-nav-menu a').count()==6
                assert '本工具只保存公开统计字段' not in page.locator('.video-overview').inner_text()
                assert '报告保存目录' not in page.locator('.video-overview').inner_text()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.get_by_role('button',name='打开 HTML 报告',exact=True).click()
            page.wait_for_url('**/videos/BV1xx411c7mD?*')
            assert panel.app.state.browser_opens
            expect(page.locator('.video-heading-content')).to_contain_text('布局验收视频')
            assert not errors
        finally:
            browser.close();server.should_exit=True;thread.join(timeout=5);sock.close()
