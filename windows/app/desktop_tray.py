from __future__ import annotations

import asyncio
from concurrent.futures import Future
import os
import threading
from typing import Callable
import webbrowser

from app.logger import logger


class DesktopTray:
    """Windows tray belongs to the server process, including hidden launcher mode."""

    def __init__(self, loop, crawl_service, port: int, request_exit: Callable[[], None], open_panel=None):
        self.loop = loop
        self.crawl_service = crawl_service
        self.url = f"http://127.0.0.1:{port}"
        self.request_exit = request_exit
        self.panel_opener = open_panel
        self.icon = None
        self.thread = None
        self._pending: Future | None = None

    def start(self) -> None:
        if os.name != "nt":
            return
        try:
            import pystray
            from PIL import Image, ImageDraw

            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            drawing = ImageDraw.Draw(image)
            drawing.rounded_rectangle((5, 5, 59, 59), radius=13, fill="#0f766e")
            drawing.rectangle((17, 19, 46, 39), outline="white", width=3)
            drawing.line((25, 47, 39, 47), fill="white", width=3)
            self.icon = pystray.Icon("bilibili-monitor", image, "B站数据监控", pystray.Menu(
                pystray.MenuItem("打开浏览器面板", self.open_panel, default=True),
                pystray.MenuItem("立即检测", self.collect_now, enabled=lambda item: self._pending is None or self._pending.done()),
                pystray.MenuItem("进入设置", self.open_settings),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出程序", self.exit_program),
            ))
            self.thread = threading.Thread(target=self._run, name="desktop-tray", daemon=True)
            self.thread.start()
        except Exception:
            logger.exception("系统托盘启动失败，仍可通过浏览器设置页退出程序")

    def _run(self) -> None:
        try:
            self.icon.run(setup=self._ready)
        except Exception:
            logger.exception("系统托盘运行失败")

    def _ready(self, icon) -> None:
        icon.visible = True
        logger.info("系统托盘已启动")

    def open_panel(self, icon=None, item=None) -> None:
        if self.panel_opener:
            self.panel_opener("/")
        else:
            webbrowser.open(self.url + "/")

    def open_settings(self, icon=None, item=None) -> None:
        if self.panel_opener:
            self.panel_opener("/settings")
        else:
            webbrowser.open(self.url + "/settings")

    def collect_now(self, icon=None, item=None) -> None:
        if self._pending is not None and not self._pending.done():
            return
        self._pending = asyncio.run_coroutine_threadsafe(self.crawl_service.collect_running_now(), self.loop)
        if self.icon:
            self.icon.update_menu()
        self._pending.add_done_callback(self._collection_finished)

    def _collection_finished(self, future: Future) -> None:
        if future.cancelled():
            return
        try:
            result = future.result()
            text = f"立即检测完成：成功 {result['success']}，失败 {result['failed']}，跳过 {result['skipped']}"
            logger.info(text)
            if self.icon:
                self.icon.notify(text, "B站数据监控")
        except Exception:
            logger.exception("托盘立即检测失败")
        finally:
            if self.icon:
                self.icon.update_menu()

    def exit_program(self, icon=None, item=None) -> None:
        self.loop.call_soon_threadsafe(self.request_exit)

    def stop(self) -> None:
        if self._pending is not None and not self._pending.done():
            self._pending.cancel()
        if self.icon:
            self.icon.visible = False
            self.icon.stop()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=3)
