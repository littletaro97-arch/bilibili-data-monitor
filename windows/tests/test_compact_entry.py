from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import create_app


def test_target_preview_does_not_add_tasks(monkeypatch):
    app=create_app()
    with TestClient(app,client=("127.0.0.1",9000),base_url="http://127.0.0.1") as client:
        before=len(app.state.repository.list_tasks())
        assert client.post("/api/task-target",data={"video_input":"123"}).json()=={"kind":"up"}
        assert client.post("/api/task-target",data={"video_input":"BV1xx411c7mD"}).json()=={"kind":"video"}
        assert client.post("/api/task-target",data={"video_input":"https://example.com/a"}).json()=={"kind":None}
        resolver=AsyncMock(return_value=("up","123"))
        monkeypatch.setattr("app.collectors.task_target.resolve_target",resolver)
        assert client.post("/api/task-target",data={"video_input":"https://b23.tv/abc"}).json()=={"kind":"up"}
        assert len(app.state.repository.list_tasks())==before
        assert "建议登录" in client.get("/").text
        for phrase in ("更新包会校验大小", "关闭窗口会隐藏到托盘"):
            assert phrase not in client.get("/settings").text
