"""Opt-in native window test; isolates all data and stops its own service."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
root = Path(tempfile.mkdtemp(prefix="bilibili-native-panel-"))
os.environ["BILIBILI_MONITOR_DATA_DIR"] = str(root)
(root / "config.toml").write_text('[app]\nhost="127.0.0.1"\nport=18770\n', encoding="utf-8")

import httpx
import uvicorn
from app.main import app
from app.desktop_panel import DesktopPanel, evergreen_installed

assert evergreen_installed(), "Evergreen runtime missing"
panel = DesktopPanel(18770)
app.state.desktop_panel = panel
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18770, log_level="warning"))
app.state.shutdown_callback = lambda: setattr(server, "should_exit", True)
result = {}

def verify():
    try:
        if "--early-exit" in sys.argv:
            for _ in range(150):
                if server.started:
                    break
                time.sleep(.02)
            result["early_exit_requested"] = True
            return
        for _ in range(150):
            if server.started and panel.window.get_current_url() == panel.url + "/":
                break
            time.sleep(.2)
        assert panel.window.evaluate_js("document.querySelector('h1').textContent") == "B站公开视频本地分析"
        result["native_dom_loaded"] = True
        panel.window.destroy()  # Actual native FormClosing, which must cancel/hide.
        for _ in range(100):
            if panel.window.evaluate_js("window.__desktopHidden") is True:
                break
            time.sleep(.05)
        assert panel.window.evaluate_js("window.__desktopHidden") is True
        result["hide_pauses_refresh"] = True
        panel.open("/settings")
        for _ in range(100):
            if panel.window.evaluate_js("Boolean(document.querySelector('#version-updates')) && window.__desktopHidden === false"):
                break
            time.sleep(.1)
        assert panel.window.evaluate_js("window.__desktopHidden") is False
        assert panel.window.evaluate_js("Boolean(document.querySelector('#version-updates'))") is True
        result["restore_settings_loaded"] = True
        assert httpx.post(panel.url + "/desktop/activate").json()["activated"]
        result["repeat_launch_activates"] = True
    except Exception as exc:
        import traceback
        traceback.print_exc()
        result["error"] = repr(exc)
    finally:
        server.should_exit = True
        (root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

threading.Thread(target=verify, daemon=True).start()
panel.run(server)
print(json.dumps({"evidence": str(root), **result}, ensure_ascii=False))
raise SystemExit(1 if "error" in result else 0)
