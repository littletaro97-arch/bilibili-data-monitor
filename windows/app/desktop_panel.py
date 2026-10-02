from __future__ import annotations

import os
import threading
import time
import webbrowser

from app.config import RUNTIME_DIR
from app.logger import logger

RUNTIME_DOWNLOAD = "https://developer.microsoft.com/microsoft-edge/webview2/#download-section"


def evergreen_installed() -> bool:
    if os.name != "nt":
        return False
    import winreg
    key = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(root, key, 0, winreg.KEY_READ | view) as handle:
                    version = winreg.QueryValueEx(handle, "pv")[0]
                if version and version != "0.0.0.0":
                    return True
            except OSError:
                continue
    return False


class DesktopPanel:
    """One Evergreen window; no bundled Chromium and no application JS API bridge."""
    def __init__(self, port: int):
        import webview
        self.webview = webview
        self.url = f"http://127.0.0.1:{port}"
        self.hidden = False
        self.exiting = False
        self.window = webview.create_window("B站数据监控", html="<p>正在启动监控服务…</p>", width=1150, height=800, min_size=(760, 560))
        self.window.events.closing += self.hide
        self.window.events.minimized += lambda: self.set_hidden(True)
        self.window.events.restored += lambda: self.set_hidden(False)
        self.window.events.loaded += self.on_loaded

    def set_hidden(self, hidden: bool) -> None:
        self.hidden = hidden
        if self.exiting or not self.window.events.loaded.is_set():
            return
        self.on_loaded()

    def on_loaded(self) -> None:
        if self.exiting:
            # CoreWebView2 now exists. Closing merely on Shown can trigger the
            # renderer's BrowserProcessId cleanup before initialization finishes.
            self.window.destroy()
            return
        try:
            # pywebview fires event callbacks just before setting their wait flag;
            # evaluate_js waits for that flag, avoiding a skipped visibility update.
            self.window.evaluate_js(f"window.__desktopHidden = {str(self.hidden).lower()};")
        except Exception:
            logger.debug("panel visibility changed before page was ready")

    def hide(self) -> bool:
        if self.exiting:
            return True
        self.set_hidden(True)
        self.window.hide()
        return False

    def open(self, path="/") -> None:
        if self.exiting:
            return
        self.window.show()
        self.window.restore()
        # get_current_url waits for loaded: querying it during early shutdown can
        # leave pywebview's startup callback waiting after the window is destroyed.
        self.window.load_url(self.url + path)
        self.set_hidden(False)

    def close(self) -> None:
        self.exiting = True
        if self.window.events.loaded.is_set():
            self.window.destroy()

    def run(self, server) -> None:
        def serve():
            try:
                server.run()
            finally:
                self.close()

        worker = threading.Thread(target=serve, name="monitor-server", daemon=True)
        worker.start()

        def ready():
            for _ in range(200):
                if self.exiting:
                    return
                if server.started:
                    self.open()
                    return
                if not worker.is_alive():
                    return
                time.sleep(.1)
            server.should_exit = True
            self.close()

        try:
            self.webview.settings["ALLOW_DOWNLOADS"] = True
            self.webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
            # Reuse an app-private profile for cache/preferences. Private mode's
            # renderer cleanup queries BrowserProcessId before early initialization.
            self.webview.start(ready, gui="edgechromium", private_mode=False, storage_path=str(RUNTIME_DIR / "webview"))
        finally:
            server.should_exit = True
            worker.join(timeout=15)


def missing_runtime_notice() -> None:
    import ctypes
    answer = ctypes.windll.user32.MessageBoxW(None,
        "自有窗口需要 Microsoft WebView2 Evergreen Runtime。\n可安装共享运行时，无需下载完整浏览器内核包。\n\n现在打开微软下载页吗？本次仍可使用浏览器面板。",
        "B站数据监控", 0x24)
    if answer == 6:
        webbrowser.open(RUNTIME_DOWNLOAD)
