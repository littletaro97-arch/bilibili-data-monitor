"""Exercise this release in an isolated install/data directory; never use real user data."""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time
import winreg
from zipfile import ZipFile

import httpx


UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{C3C19C03-7F8E-48E4-95F3-B497EB0C6AE6}_is1"


def registered() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY):
            return True
    except FileNotFoundError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()
    if registered():
        raise RuntimeError("An existing installed copy is registered; refusing to replace its registration")
    root = Path(tempfile.mkdtemp(prefix="bilibili-installer-"))
    install = root / "中文安装目录"
    profile = root / "中文用户目录"
    data = profile / "BilibiliMonitor" / "runtime-data"
    data.mkdir(parents=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = data / "config.toml"
    config.write_text(f'[app]\nport = {port}\n', encoding="utf-8")
    env = dict(os.environ, LOCALAPPDATA=str(profile))
    env.pop("BILIBILI_MONITOR_DATA_DIR", None)
    base = f"http://127.0.0.1:{port}"
    install_args = [str(args.installer.resolve()), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/CLOSEAPPLICATIONS=no", f"/DIR={install}", f"/GROUP=BilibiliMonitor-test-{root.name}"]
    checks = []

    def install_once(label: str) -> None:
        subprocess.run([*install_args, f"/LOG={root / (label + '.log')}"], check=True, timeout=180)
        assert (install / "BilibiliMonitor.exe").exists()
        assert registered()
        assert not list(install.rglob("*.db")), "User database must not be included"
        checks.append(label)

    def launch() -> subprocess.Popen:
        process = subprocess.Popen([str(install / "BilibiliMonitor.exe"), "--server"], env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(90):
            if process.poll() is not None:
                raise RuntimeError(f"Packaged app exited early: {process.returncode}; see {root}")
            try:
                if httpx.get(base + "/api/logs", timeout=2).status_code == 200:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(1)
        process.terminate()
        raise TimeoutError(f"Packaged app did not start; see {root}")

    def stop(process: subprocess.Popen) -> None:
        response = httpx.post(base + "/shutdown", timeout=10)
        assert response.status_code == 200
        process.wait(timeout=15)

    def uninstall(label: str) -> None:
        subprocess.run([str(install / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={root / (label + '.log')}"], check=True, timeout=90)
        # Inno uninstaller finishes cleanup in its child process.
        for _ in range(30):
            if not (install / "BilibiliMonitor.exe").exists() and not registered():
                break
            time.sleep(1)
        assert not (install / "BilibiliMonitor.exe").exists()
        assert not registered()
        checks.append(label)

    with (root / "app.log").open("wb") as log:
        install_once("fresh-install")
        process = launch()
        try:
            for route in ["/", "/settings", "/assets/plotly.min.js"]:
                response = httpx.get(base + route, timeout=30)
                assert response.status_code == 200, (route, response.text[:200])
                if route == "/settings":
                    assert "run.bat" not in response.text
            checks.append("homepage-settings-plotly")
            database = data / "data" / "bilibili_local.db"
            with sqlite3.connect(database) as conn:
                now = "2026-01-01T00:00:00+00:00"
                conn.execute("INSERT INTO videos (bvid,title,created_at,updated_at) VALUES (?,?,?,?)", ("BV1xx411c7mD", "安装包测试", now, now))
                for stamp, count in [(now, 1), ("2026-01-01T01:00:00+00:00", 5)]:
                    conn.execute("INSERT INTO video_stats_snapshot (bvid,captured_at,view_count,like_count,source_type,collection_source) VALUES (?,?,?,?,?,?)", ("BV1xx411c7mD", stamp, count, 1, "collected", "MANUAL"))
            assert httpx.get(base + "/videos/BV1xx411c7mD", timeout=30).status_code == 200
            response = httpx.post(base + "/videos/BV1xx411c7mD/report", follow_redirects=True, timeout=30)
            assert response.status_code == 200
            reports = list((data / "reports" / "output").glob("*.html"))
            assert reports and "Plotly.newPlot" in reports[0].read_text(encoding="utf-8")
            archive = httpx.get(base + "/history-exchange/export", timeout=30)
            assert archive.status_code == 200
            with ZipFile(BytesIO(archive.content)) as z:
                manifest = json.loads(z.read("manifest.json"))
                assert manifest["recordCounts"] == {"videos": 1, "snapshots": 2}
            assert httpx.post(base + "/settings/launcher", data={"show_console": "on"}, timeout=10).status_code == 303
            assert "show_console = true" in config.read_text(encoding="utf-8")
            checks.append("report-export-config-write")
        finally:
            stop(process)
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        install_once("upgrade-reinstall")
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before
        process = launch()
        assert httpx.get(base + "/videos/BV1xx411c7mD", timeout=30).status_code == 200
        stop(process)
        before = {str(p.relative_to(data)): hashlib.sha256(p.read_bytes()).hexdigest() for p in data.rglob("*") if p.is_file()}
        uninstall("uninstall")
        after = {str(p.relative_to(data)): hashlib.sha256(p.read_bytes()).hexdigest() for p in data.rglob("*") if p.is_file()}
        assert before == after
        checks.append("all-user-data-retained")
    result = {"result": "PASS", "checks": checks, "evidence_directory": str(root), "visual_wizard_verification": "separate manual report"}
    (root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
