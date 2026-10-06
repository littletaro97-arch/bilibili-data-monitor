import os
from datetime import datetime,timedelta
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from app.database import Database,Repository,local_now
from app.models import VideoInfo,VideoComment,DanmakuItem,RateLimitError

BV='BV1xx411c7mD'


def repo_at(tmp_path):
    db=Database(tmp_path/'controls.db');db.initialize();repo=Repository(db)
    repo.upsert_video(VideoInfo(BV,title='控制测试',cid=10))
    return repo


def test_interval_edit_preserves_pause_and_cooldown_and_inflight_uses_new_value(tmp_path):
    repo=repo_at(tmp_path);identity=repo.create_task(BV,300,60,10)
    with repo.database.connect() as c:c.execute("UPDATE crawl_tasks SET status='paused',cooldown_until='2099-01-01T00:00:00+08:00',consecutive_failures=3 WHERE id=?",(identity,))
    repo.set_task_interval(identity,900,60)
    row=repo.get_task(identity)
    assert row['interval_seconds']==900 and row['status']=='paused' and row['consecutive_failures']==3
    assert row['cooldown_until'].startswith('2099')
    assert datetime.fromisoformat(row['next_run_at'])>local_now()+timedelta(seconds=890)
    repo.mark_success(BV,300)
    assert datetime.fromisoformat(repo.get_task(identity)['next_run_at'])>local_now()+timedelta(seconds=890)
    for value in [59,0,-1,31536001,True]:
        with pytest.raises(RateLimitError):repo.set_task_interval(identity,value,60)
    repo.set_task_status(identity,'stopped')
    with pytest.raises(RateLimitError):repo.set_task_interval(identity,60,60)


def test_visibility_is_observation_not_absence_or_claimed_deletion(tmp_path):
    repo=repo_at(tmp_path)
    repo.insert_comments([VideoComment(BV,'1',message='保留原文')],captured_at='2026-10-04T10:00:00+08:00')
    repo.insert_comments([])
    assert repo.list_comments(BV)[0]['visibility']=='observed'
    repo.insert_comments([VideoComment(BV,'1',message='[已删除]')])
    row=repo.list_comments(BV)[0]
    assert row['visibility']=='placeholder' and row['message']=='保留原文'
    repo.insert_comments([VideoComment(BV,'1',message='重新公开')])
    assert repo.list_comments(BV)[0]['visibility']=='observed'
    repo.insert_comments([VideoComment(BV,'local-comment-1',message='[已删除]')])
    assert next(r for r in repo.list_comments(BV) if r['rpid']=='local-comment-1')['visibility']=='unknown'
    repo.insert_danmaku([DanmakuItem(BV,10,1,'仍保留',source_id='1')])
    repo.insert_danmaku([])
    assert repo.text_dashboard_data(BV)['danmaku'][0]['visibility']=='observed'


@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in browser')
def test_prepaint_layout_auto_preferences_animated_highlight_and_interval_dialog(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    from app.main import create_app
    repo=repo_at(tmp_path);identity=repo.create_task(BV,300,60,10)
    app=create_app();app.state.repository=repo
    client=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')
    def serve(route):
        req=route.request;response=client.request(req.method,urlsplit(req.url).path,content=req.post_data,headers={'Content-Type':req.headers.get('content-type','')})
        route.fulfill(status=response.status_code,headers={k:v for k,v in response.headers.items() if k.lower() not in {'content-length','content-encoding'}},body=response.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1280,'height':1000});page.route('**/*',serve)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script('''window.firstMain=null;
              new MutationObserver(()=>{const m=document.querySelector('main.detail-page');if(m&&!firstMain)firstMain={enabled:document.documentElement.dataset.detailNav,padding:getComputedStyle(m).paddingRight};}).observe(document,{childList:true,subtree:true});''')
            page.goto('http://127.0.0.1/')
            buttons=page.locator('.task-foot button').all_text_contents()
            assert buttons[:3]==['立即采集','修改采集时间','暂停']
            page.get_by_role('button',name='修改采集时间').click()
            expect(page.get_by_role('dialog',name='修改采集时间')).to_be_visible()
            assert page.url=='http://127.0.0.1/'
            page.locator('#task-interval').fill('900')
            with page.expect_response('**/tasks/'+str(identity)+'/interval'):
                page.get_by_role('dialog',name='修改采集时间').locator('button[type=submit]').click()
            assert repo.get_task(identity)['interval_seconds']==900
            page.goto('http://127.0.0.1/settings')
            assert page.locator('#navigation-preferences button').count()==0
            page.locator('#navigation-side').select_option('left')
            page.locator('#navigation-enabled').uncheck()
            page.goto(f'http://127.0.0.1/videos/{BV}')
            assert page.evaluate('firstMain')=={'enabled':'false','padding':'24px'}
            expect(page.locator('#floating-nav')).to_be_hidden()
            page.goto('http://127.0.0.1/settings');page.locator('#navigation-enabled').check();page.locator('#navigation-side').select_option('right')
            page.goto(f'http://127.0.0.1/videos/{BV}')
            assert page.evaluate('firstMain')=={'enabled':'true','padding':'166px'}
            expect(page.locator('#floating-nav')).to_be_visible()
            page.locator('#floating-nav-menu a').nth(1).click()
            assert page.locator('.nav-highlight').evaluate('e=>getComputedStyle(e).transitionTimingFunction').startswith('cubic-bezier')
            assert page.locator('.inspection-scope').count()==0
            details=page.locator('details[data-chart-panel=single]');details.locator(':scope > summary').click()
            timing=details.locator(':scope > .details-body').evaluate('e=>e.getAnimations()[0]?.effect.getTiming().easing')
            assert timing=='cubic-bezier(0.4, 0, 0.2, 1)'
            assert not errors
        finally:browser.close()
