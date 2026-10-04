from fastapi.testclient import TestClient


def test_auto_settings_json_saves_and_reports_validation(monkeypatch):
    from app.main import create_app
    from app.ui import pages
    writes=[]
    monkeypatch.setattr(pages,'save_launcher_settings',lambda **kw:writes.append(kw))
    def save_lan(**kw):
        if kw['enabled'] and not kw['password']:raise ValueError('请先设置密码')
        writes.append(kw)
    monkeypatch.setattr(pages,'save_lan_settings',save_lan)
    client=TestClient(create_app(),client=('127.0.0.1',9000))
    headers={'Accept':'application/json'}
    assert client.post('/settings/launcher',data={'show_console':'on'},headers=headers).status_code==200
    assert writes[-1]=={'show_console':True}
    r=client.post('/settings/lan',data={'enabled':'on'},headers=headers)
    assert r.status_code==400 and r.json()['error']=='请先设置密码'
    r=client.post('/settings/lan',data={'enabled':'on','password':'test-only-password'},headers=headers)
    assert r.status_code==200 and '重启' in r.json()['message']
    settings=client.get('/settings').text
    assert '保存启动设置' not in settings and '保存局域网设置' not in settings
    assert '<details open class="manual-session">' in settings

import os
import pytest

@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in browser')
def test_settings_autosave_and_overview_geometry(monkeypatch,tmp_path):
    from urllib.parse import urlsplit
    from playwright.sync_api import sync_playwright,expect
    from app.main import create_app
    from app.ui import pages
    from app.database import Database,Repository
    from app.models import VideoInfo
    writes=[]
    monkeypatch.setattr(pages,'save_launcher_settings',lambda **kw:writes.append(kw))
    monkeypatch.setattr(pages,'save_lan_settings',lambda **kw:writes.append(kw))
    db=Database(tmp_path/'layout.db');db.initialize();repo=Repository(db)
    repo.upsert_video(VideoInfo('BV1xx411c7mD',title='布局测试'))
    app=create_app();app.state.repository=repo
    client=TestClient(app,client=('127.0.0.1',9000))
    def serve(route):
        req=route.request
        response=client.request(req.method,urlsplit(req.url).path,content=req.post_data,headers={'Content-Type':req.headers.get('content-type',''),'Accept':req.headers.get('accept','')})
        route.fulfill(status=response.status_code,headers={k:v for k,v in response.headers.items() if k.lower() not in {'content-length','content-encoding'}},body=response.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1600,'height':1000});page.route('**/*',serve)
            page.goto('http://127.0.0.1/settings')
            assert page.locator('.manual-session').get_attribute('open') is not None
            enabled=not page.locator('#show-console').is_checked()
            page.locator('#show-console').set_checked(enabled)
            expect(page.locator('[data-save-status]').first).to_contain_text('已自动保存')
            assert writes[-1]=={'show_console':enabled}
            page.locator('#password').fill('test-only-password');page.locator('#password').blur()
            expect(page.locator('[data-save-status]').nth(1)).to_contain_text('已自动保存')
            assert writes[-1]['password']=='test-only-password'
            page.locator('#show-password').check()
            assert page.locator('#password').get_attribute('type')=='text'
            page.goto('http://127.0.0.1/videos/BV1xx411c7mD')
            page.wait_for_timeout(250)
            cells=page.locator('.video-metadata .metric');boxes=[cells.nth(i).bounding_box() for i in range(4)]
            link=page.locator('.overview-links a').bounding_box();report=page.locator('.overview-links button').bounding_box()
            assert boxes[0]['x']==boxes[2]['x'] and boxes[1]['x']==boxes[3]['x']
            assert link['x']>boxes[1]['x'] and abs(link['y']-boxes[0]['y'])<1
            assert abs(report['y']-boxes[2]['y'])<1
            page.set_viewport_size({'width':480,'height':900})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        finally:browser.close()
