from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import webbrowser

from app.config import BASE_DIR, RUNTIME_DIR, load_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detached", action="store_true")
    parser.add_argument("--open-browser-only", action="store_true")
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.server:
        from app.main import main as server_main
        server_main()
        return 0
    if args.no_browser:
        from app.main import main as server_main
        server_main(desktop=False)
        return 0

    current = load_settings()
    if args.open_browser_only:
        _open_when_ready(current.app.port, _local_url(current.app.port))
        return 0

    if not current.launcher.show_console and not args.detached:
        return _start_detached_launcher()

    return _run_visible() if current.launcher.show_console else _run_hidden()


def _run_visible() -> int:
    current = load_settings()
    url = _local_url(current.app.port)
    if _port_is_open(current.app.port):
        print(f"端口 {current.app.port} 已被占用。")
        print(f"如果程序已经在运行，将打开 {url}")
        _activate_existing(current.app.port, url)
        _pause()
        return 0

    try:
        return subprocess.call(_command("app.main"), cwd=BASE_DIR)
    finally:
        _pause()


def _run_hidden() -> int:
    current = load_settings()
    url = _local_url(current.app.port)
    if _port_is_open(current.app.port):
        _activate_existing(current.app.port, url)
        return 0

    log_path = RUNTIME_DIR / "logs" / "launcher.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            _command("app.main"),
            cwd=BASE_DIR,
            creationflags=_creationflags(hidden=True),
            stdout=log,
            stderr=log,
        )

    for _ in range(30):
        if process.poll() is not None or _port_is_open(current.app.port):
            break
        time.sleep(1)
    return 0


def _activate_existing(port: int, url: str) -> None:
    import httpx
    try:
        response = httpx.post(f"http://127.0.0.1:{port}/desktop/activate", timeout=3)
        if response.status_code == 200 and response.json().get("activated"):
            return
    except (httpx.HTTPError, ValueError):
        pass
    webbrowser.open(url)


def _start_detached_launcher() -> int:
    pythonw = _pythonw_path()
    subprocess.Popen(
        _command("app.launcher", "--detached", executable=pythonw),
        cwd=BASE_DIR,
        creationflags=_creationflags(detached=True, hidden=True),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return 0


def _open_when_ready(port: int, url: str, process: subprocess.Popen | None = None) -> None:
    for _ in range(30):
        if process is not None and process.poll() is not None:
            return
        if _port_is_open(port):
            webbrowser.open(url)
            return
        time.sleep(1)


def _port_is_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _local_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/"


def _pythonw_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    executable = Path(sys.executable)
    candidate = executable.with_name("pythonw.exe")
    if os.name == "nt" and candidate.exists():
        return str(candidate)
    return sys.executable


def _command(module: str, *args: str, executable: str | None = None) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *(["--server"] if module == "app.main" else []), *args]
    return [executable or sys.executable, "-m", module, *args]


def _creationflags(*, hidden: bool = False, detached: bool = False) -> int:
    if os.name != "nt":
        return 0
    flags = 0
    if hidden:
        flags |= subprocess.CREATE_NO_WINDOW
    if detached:
        flags |= subprocess.DETACHED_PROCESS
    return flags


def _pause() -> None:
    if os.name != "nt":
        return
    try:
        input("按回车键关闭此窗口...")
    except EOFError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
