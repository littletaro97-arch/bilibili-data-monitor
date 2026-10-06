from pathlib import Path
import pytest
from app.models import AppError
from unittest.mock import Mock
from fastapi.testclient import TestClient
from app.database import Database,Repository
from app.models import VideoInfo
from app.services.report_service import ReportService
from app.main import create_app

BV='BV1xx411c7mD'
def panel_at(tmp_path):
 db=Database(tmp_path/'reports.db');db.initialize();repo=Repository(db);repo.upsert_video(VideoInfo(BV,title='报告测试'))
 app=create_app();app.state.repository=repo;app.state.report_service=ReportService(repo,tmp_path/'reports',Path(__file__).parents[1]/'app/reports/templates')
 return TestClient(app,client=('127.0.0.1',9000),base_url='http://127.0.0.1')

def test_report_external_open_move_warning_delete_and_no_log_resurrection(tmp_path,monkeypatch):
 client=panel_at(tmp_path);service=client.app.state.report_service;browser=Mock(return_value=True)
 monkeypatch.setattr('app.services.report_service.webbrowser.open',browser)
 response=client.post(f'/videos/{BV}/report',data={'open_report':'true'},follow_redirects=False)
 assert response.status_code==303 and response.headers['location'].startswith('/videos/')
 path=next(service.output_dir.glob('*.html'));browser.assert_called_once()
 assert browser.call_args.args[0].endswith('/reports/'+path.name)
 assert '删除报告' in client.get(f'/videos/{BV}').text
 moved=path.rename(tmp_path/'moved.html')
 assert not service.recent(BV)[0]['available']
 assert '路径已改变' in client.get(f'/videos/{BV}').text
 assert client.get('/reports/'+path.name).status_code==404
 assert client.post('/reports/'+path.name+'/delete',follow_redirects=False).status_code==303
 assert service.recent(BV)==[] and moved.exists()
 assert client.post('/reports/evil.txt/delete',follow_redirects=False).status_code==303
 assert moved.exists()

def test_delete_only_target_report_and_remote_browser_denied(tmp_path,monkeypatch):
 client=panel_at(tmp_path);service=client.app.state.report_service
 for invalid in ["..\\escape", "../escape", "unknown"]:
  with pytest.raises(AppError):service.generate(invalid)
 first=service.generate(BV);second=service.generate(BV)
 assert first!=second
 client.post('/reports/'+first.name+'/delete')
 assert not first.exists() and second.exists()
 remote=TestClient(client.app,client=('192.168.1.20',9000),base_url='http://127.0.0.1')
 assert remote.post('/reports/'+second.name+'/open').status_code==403
 assert remote.post('/reports/'+second.name+'/delete').status_code==403
