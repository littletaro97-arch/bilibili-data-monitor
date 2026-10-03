"""Native WebView2 UI regression check; isolated data, no real collection/config writes."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch

root = Path(tempfile.mkdtemp(prefix="bilibili-settings-ui-"))
os.environ["BILIBILI_MONITOR_DATA_DIR"] = str(root)
(root / "config.toml").write_text('[app]\nport=18774\n[launcher]\nshow_console=false\n', encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from app.main import app
from app.desktop_panel import DesktopPanel
from app.desktop_tray import DesktopTray
from app.models import VideoInfo

for bvid in ["BV1xx411c7mD", "BV1yy411c7mD", "BV1zz411c7mD"]:
    app.state.repository.upsert_video(VideoInfo(bvid, title="布局验收任务"))
    task_id = app.state.repository.create_task(bvid, 300, min_interval=60, max_active=10)
    app.state.repository.set_task_status(task_id, "paused")
panel = DesktopPanel(18774)
app.state.desktop_panel = panel
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18774, log_level="warning"))
result = {}

def wait(expression):
    for _ in range(200):
        if panel.window.events.loaded.wait(.1):
            try:
                if panel.window.evaluate_js(expression):
                    return
            except Exception:
                pass
        time.sleep(.05)
    raise AssertionError(expression)

def js(code):
    return panel.window.evaluate_js(code)

def box(selector):
    return js(f"(() => {{ const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return {{x:r.x,y:r.y,width:r.width,height:r.height}}; }})()")

def go(path):
    panel.open(path)
    wait(f"location.pathname === {json.dumps(path)} && !!document.querySelector('main')")

def verify():
    try:
        wait("location.pathname === '/' && !!document.querySelector('.task-card')")
        assert js("document.documentElement.scrollHeight > document.documentElement.clientHeight")
        result["home_nav"] = box("header nav")
        go("/recycle-bin")
        result["recycle_nav"] = box("header nav")
        assert result["home_nav"] == result["recycle_nav"], "Navigation shifts with scrollbar"
        result["recycle_return"] = box(".page-actions")
        js("document.querySelector('.page-actions a').click()")
        wait("location.pathname === '/' && !!document.querySelector('.task-card')")
        result["return_home_works"] = True
        go("/settings")
        assert box(".page-actions") == result["recycle_return"], "Return action position differs"
        assert js("document.querySelectorAll('.switch-card input[role=switch]').length") == 3
        assert js("!document.querySelector('#show-console').checked")
        js("document.querySelector('label[for=show-console] .switch-title').click()")
        assert js("new FormData(document.querySelector('#show-console').form).get('show_console')") == "on"
        js("document.querySelector('#show-console').click()")
        assert js("!new FormData(document.querySelector('#show-console').form).has('show_console')")
        js("document.querySelector('#show-password').click()")
        assert js("document.querySelector('#password').type") == "text"
        js("document.querySelector('#show-password').click()")
        assert js("document.querySelector('#password').type") == "password"
        js("document.querySelector('#lan-enabled').click()")
        assert js("new FormData(document.querySelector('#lan-enabled').form).get('enabled')") == "on"
        js("document.querySelector('[data-theme-toggle]').click()")
        assert js("document.documentElement.dataset.theme") == "dark"
        result["dark_track_color"] = js("getComputedStyle(document.querySelector('#lan-enabled + .switch-track')).backgroundColor")
        js("document.querySelector('[data-theme-toggle]').click()")
        assert js("document.documentElement.dataset.theme") == "light"
        result["light_track_color"] = js("getComputedStyle(document.querySelector('#lan-enabled + .switch-track')).backgroundColor")
        assert result["light_track_color"] != result["dark_track_color"]
        assert 'show_console=false' in (root / "config.toml").read_text(encoding="utf-8")
        result["switch_label_form_theme_password_checks"] = True
        result["success"] = True
    except Exception as exc:
        import traceback
        traceback.print_exc()
        result["error"] = repr(exc)
    finally:
        (root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        server.should_exit = True

with patch.object(app.state.scheduler, "start"), patch.object(app.state.scheduler, "shutdown"), patch.object(DesktopTray, "start"):
    threading.Thread(target=verify, daemon=True).start()
    panel.run(server)
print(json.dumps({"evidence": str(root), **result}, ensure_ascii=False, indent=2))
raise SystemExit(0 if result.get("success") else 1)
