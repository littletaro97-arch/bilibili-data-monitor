import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app.database import Database, Repository
from app.models import DanmakuItem, VideoComment, VideoInfo, VideoStats
from app.models import ProviderError
from app.collectors.provider import BilibiliWebProvider
from app.services.text_inspection import build_text_panel
from app.services.phase2_service import Phase2Service
from app.collectors.provider import MockVideoDataProvider


def repository(tmp_path):
    db=Database(tmp_path / 'text.db');db.initialize();repo=Repository(db)
    repo.upsert_video(VideoInfo('BV1xx411c7mD', title='检视台测试', aid=123, cid=10))
    return repo


def test_unique_samples_scope_and_limit(tmp_path):
    repo=repository(tmp_path)
    row=DanmakuItem('BV1xx411c7mD', cid=10, text='热点', progress_sec=1, send_time=100)
    repo.insert_danmaku([row,row,DanmakuItem('BV1xx411c7mD',cid=11,text='另一P',progress_sec=2)])
    raw=repo.text_dashboard_data('BV1xx411c7mD',limit=1)
    assert raw['raw_danmaku']==3 and raw['stored_danmaku']==2 and raw['truncated']
    panel=build_text_panel(raw,repo.get_video('BV1xx411c7mD'),None)
    assert panel['duplicates']==1 and not panel['complete']


def test_different_platform_ids_are_not_merged(tmp_path):
    repo=repository(tmp_path)
    rows=[DanmakuItem('BV1xx411c7mD',cid=10,text='一样',progress_sec=1,send_time=100,source_id=str(i)) for i in range(2)]
    repo.insert_danmaku(rows+rows+[DanmakuItem('BV1xx411c7mD',cid=10,text='一样',progress_sec=1,send_time=100)])
    raw=repo.text_dashboard_data('BV1xx411c7mD')
    assert raw['stored_danmaku']==2 and raw['raw_danmaku']==5


@pytest.mark.asyncio
@pytest.mark.parametrize('target,expected', [(None,10),(11,11)])
async def test_default_and_selected_part_are_isolated(tmp_path,target,expected):
    class Provider(MockVideoDataProvider):
        async def fetch_danmaku_parts(self,bvid):
            return [{'cid':10,'page':1},{'cid':11,'page':2}]
    repo=repository(tmp_path);service=Phase2Service(repo,Provider(),20,5)
    assert await service.collect_danmaku_once('BV1xx411c7mD',target)==1
    rows=repo.list_danmaku('BV1xx411c7mD')
    assert len(rows)==1 and rows[0]['cid']==expected


@pytest.mark.asyncio
async def test_other_video_cid_is_rejected(tmp_path):
    class Provider(MockVideoDataProvider):
        async def fetch_danmaku_parts(self,bvid): return [{'cid':10,'page':1}]
    repo=repository(tmp_path);service=Phase2Service(repo,Provider(),20,5)
    with pytest.raises(ProviderError,match='不属于'):
        await service.collect_danmaku_once('BV1xx411c7mD',999)
    assert not repo.list_danmaku('BV1xx411c7mD')


@pytest.mark.asyncio
async def test_xml_preserves_platform_id_as_text():
    class Client:
        async def get_text(self,url): return '<i><d p="1.2,1,25,16777215,1710,0,hash,9007199254740993,11">文本</d></i>'
    rows=await BilibiliWebProvider(Client()).fetch_danmaku('BV1xx411c7mD',10)
    assert rows[0].source_id=='9007199254740993'


@pytest.mark.asyncio
async def test_each_part_collected_and_scope_recorded(tmp_path):
    class Provider(MockVideoDataProvider):
        async def fetch_danmaku_parts(self,bvid):
            return [{'cid':10,'page':1,'duration':60,'name':'P1'},{'cid':11,'page':2,'duration':60,'name':'P2'}]
    repo=repository(tmp_path);service=Phase2Service(repo,Provider(),20,5)
    assert await service.collect_danmaku_once('BV1xx411c7mD', all_parts=True)==2
    run=repo.text_dashboard_data('BV1xx411c7mD')['runs'][0]
    assert len(run['metadata']['parts'])==2 and run['metadata']['total_parts']==2
    assert not run['metadata']['complete']


@pytest.mark.skipif(os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST')!='1',reason='opt-in headless rendering')
def test_dashboard_keywords_parts_peaks_pagination_and_safe_text(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    from app.main import create_app
    repo=repository(tmp_path);bvid='BV1xx411c7mD'
    repo.insert_snapshot(VideoStats(bvid,reply_count=10000,danmaku_count=30000))
    rows=[DanmakuItem(bvid,cid=10,text=f'风神 热点 {i}',progress_sec=i%200,send_time=1710000000+i) for i in range(600)]
    rows.extend([DanmakuItem(bvid,cid=11,text='另外一个分P',progress_sec=2),DanmakuItem(bvid,cid=10,text='本地演示',progress_sec=5,raw_text='local')])
    repo.insert_danmaku(rows)
    repo.insert_danmaku(rows[:1])
    repo.insert_comments([VideoComment(bvid,rpid='a',message='<img src=x onerror=alert(1)> 风神',like_count=50),VideoComment(bvid,rpid='local-comment-1',message='导入评论',like_count=999)])
    repo.record_text_collection(bvid,'danmaku',{'parts':[{'cid':10,'page':1,'name':'第一P','duration':215},{'cid':11,'page':2,'name':'第二P','duration':220}],'total_parts':2,'interrupted':False,'complete':False})
    app=create_app();app.state.repository=repo
    client=TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')
    def serve(route):
        response=client.get(urlsplit(route.request.url).path)
        route.fulfill(status=response.status_code,headers={k:v for k,v in response.headers.items() if k.lower() not in {'content-length','content-encoding'}},body=response.content)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1280,'height':1000});page.route('**/*',serve)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1/videos/{bvid}');root=page.locator('#text-inspection')
            expect(root.locator('.inspection-kpi').first).to_contain_text('600')
            assert root.locator('.inspection-item').count()==50
            page.locator('#text-next').click();expect(page.locator('#text-page')).to_contain_text('2 / 12')
            page.locator('#text-keyword').fill('风神 missing');page.locator('#text-match').select_option('all')
            expect(page.locator('#text-list-scope')).to_contain_text('符合条件 0 条')
            page.locator('#text-match').select_option('any');expect(page.locator('#text-list-scope')).to_contain_text('符合条件 600 条')
            page.locator('#text-reset').click();page.locator('#text-peaks button').first.click()
            expect(page.locator('#text-clear-range')).to_be_visible()
            assert root.locator('.inspection-item').count()<=50
            page.locator('#text-clear-range').click();page.locator('#text-part').select_option('11')
            assert page.locator('#text-collect-cid').input_value()=='11'
            assert page.locator('#text-collect-form select[name=scope]').input_value()=='selected'
            expect(page.locator('#text-list')).to_contain_text('另外一个分P')
            page.locator('#text-part').select_option('10');root.screenshot(path=str(tmp_path/'inspection-light.png'))
            expect(page.locator('#text-words')).to_contain_text('风神')
            page.locator('#text-words button').filter(has_text='风神').click()
            expect(page.locator('#text-list-scope')).to_contain_text('符合条件 600 条')
            page.get_by_text('补充分词专名',exact=True).click()
            page.locator('#text-dictionary').fill('风神热点')
            page.locator('#text-dictionary-form button').click()
            expect(page.locator('#text-dictionary-status')).to_contain_text('已保存 1 个专名')
            page.reload()
            assert page.locator('#text-dictionary').input_value()=='风神热点'
            page.get_by_text('补充分词专名',exact=True).click()
            page.locator('#text-dictionary').fill('<img>')
            page.locator('#text-dictionary-form button').click()
            expect(page.locator('#text-dictionary-status')).to_contain_text('每词 2–30 字')
            page.locator('[data-theme-toggle]').click()
            expect(page.locator('#text-filter button[type=submit]')).to_have_css('color','rgb(20, 41, 36)')
            root.screenshot(path=str(tmp_path/'inspection-dark.png'))
            page.locator('#tab-comments').click();expect(page.locator('#text-density')).to_be_hidden()
            expect(page.locator('#text-list')).to_contain_text('<img src=x onerror=alert(1)>')
            assert page.locator('#text-list img').count()==0
            expect(page.locator('#text-kpis')).not_to_contain_text('999')
            page.locator('#text-origin').select_option('local');expect(page.locator('#text-list')).to_contain_text('导入评论')
            page.set_viewport_size({'width':390,'height':844})
            assert root.evaluate('e => e.scrollWidth <= e.clientWidth')
            assert not errors
        finally:browser.close()
