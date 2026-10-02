"""Opt-in real WebView benchmark on a SQLite backup; never collects real tasks.

Requires psutil in the development environment, not in the shipped application.
Run before/after with the same --fixture database and distinct --output paths.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from unittest.mock import patch

import psutil

parser = argparse.ArgumentParser()
parser.add_argument('--fixture', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
root = Path(tempfile.mkdtemp(prefix='bilibili-performance-'))
(root / 'data').mkdir()
with sqlite3.connect(Path(args.fixture).resolve().as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(root / 'data/bilibili_local.db') as target:
    source.backup(target)
os.environ['BILIBILI_MONITOR_DATA_DIR'] = str(root)
(root / 'config.toml').write_text('[app]\nport=18772\n', encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from app.main import app
from app.desktop_panel import DesktopPanel

panel = DesktopPanel(18772)
app.state.desktop_panel = panel
server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=18772, log_level='warning'))
app.state.shutdown_callback = lambda: setattr(server, 'should_exit', True)
result = {'isolated_runtime': str(root), 'logical_cpus': psutil.cpu_count(), 'scenes': {}}

def sample():
    processes = [psutil.Process(), *psutil.Process().children(recursive=True)]
    cpu = rss = private = 0
    for process in processes:
        try:
            cpu += sum(process.cpu_times()[:2])
            info = process.memory_info()
            rss += info.rss
            private += info.private
        except psutil.NoSuchProcess:
            pass
    return cpu, rss / 1048576, private / 1048576

def wait_js(expression):
    for _ in range(200):
        if not panel.window.events.loaded.wait(.1):
            continue
        try:
            if panel.window.evaluate_js(expression):
                return
        except Exception:
            pass
        time.sleep(.1)
    raise AssertionError(expression)

def scene(name):
    time.sleep(3)
    before = sample()
    start = time.perf_counter()
    time.sleep(15)
    after = sample()
    result['scenes'][name] = {
        'working_mib': round(after[1], 1), 'private_mib': round(after[2], 1),
        'cpu_seconds': round(after[0] - before[0], 3),
        'cpu_machine_percent': round((after[0] - before[0]) / (time.perf_counter() - start) / psutil.cpu_count() * 100, 3),
        'rendered_charts': panel.window.evaluate_js("Array.from(document.querySelectorAll('.plotly-graph-div')).filter(c => !!c.layout).length"),
        'chart_debug': panel.window.evaluate_js("Array.from(document.querySelectorAll('.lazy-chart-target')).map(c => ({text: c.textContent.slice(0,40), initialized: !!c.layout, color: c.layout?.font?.color}))"),
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

def verify():
    try:
        wait_js("location.pathname === '/' && !!document.querySelector('h1')")
        scene('home')
        bv = app.state.repository.list_tasks()[0]['bvid']
        panel.open('/videos/' + bv)
        wait_js("!!document.querySelector('[data-video-cover]')")
        scene('detail_collapsed')
        panel.window.evaluate_js("const section=document.querySelector('[data-chart-panel=dual-axis]'); section.open=true; section.scrollIntoView()")
        wait_js("Array.from(document.querySelectorAll('.plotly-graph-div')).some(c => !!c.layout)")
        scene('detail_one_chart')
        panel.window.evaluate_js("window.savedChartData=document.querySelector('.js-plotly-plot').data")
        panel.window.evaluate_js("document.querySelector('[data-chart-panel=dual-axis]').open=false")
        scene('detail_closed_again')
        panel.window.evaluate_js("document.querySelector('[data-chart-panel=dual-axis]').open=true")
        wait_js("Array.from(document.querySelectorAll('.plotly-graph-div')).some(c => !!c.layout)")
        result['chart_instance_reused'] = panel.window.evaluate_js("document.querySelector('.js-plotly-plot').data === window.savedChartData")
        panel.window.evaluate_js("document.querySelector('[data-theme-toggle]').click()")
        wait_js("!!document.querySelector('.js-plotly-plot') && Array.from(document.querySelectorAll('.js-plotly-plot')).every(c => c.layout?.font?.color === getComputedStyle(document.documentElement).getPropertyValue('--text').trim())")
        result['chart_reopen_and_theme'] = True
        panel.window.evaluate_js("document.querySelector('[data-chart-panel=dual-axis]').open=false")
        result['cover_loaded'] = panel.window.evaluate_js("document.querySelector('[data-video-cover]').naturalWidth > 0")
        if panel.window.evaluate_js("document.querySelector('[data-video-cover]').src.startsWith(location.origin)"):
            panel.window.evaluate_js("window.coverProbe=null; const cover=document.querySelector('[data-video-cover]'); const start=performance.now(); fetch(cover.src).then(r => r.blob()).then(blob => {window.coverProbe={milliseconds:performance.now()-start, bytes:blob.size}})")
            wait_js("window.coverProbe !== null")
            result['warm_cover_fetch'] = panel.window.evaluate_js("window.coverProbe")
        result['cover_resources'] = panel.window.evaluate_js("performance.getEntriesByType('resource').filter(r => r.initiatorType === 'img' || r.name.includes('/covers/')).map(r => ({url: r.name, milliseconds: r.duration, transfer_bytes: r.transferSize}))")
        panel.hide()
        time.sleep(1)
        scene('tray')
        result['success'] = True
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        server.should_exit = True

with patch.object(app.state.scheduler, 'start'), patch.object(app.state.scheduler, 'shutdown'):
    worker = threading.Thread(target=verify, daemon=True)
    worker.start()
    panel.run(server)
print(json.dumps({**result, 'scenes': {name: {k: v for k, v in scene.items() if k != 'chart_debug'} for name, scene in result['scenes'].items()}}, ensure_ascii=False, indent=2))
raise SystemExit(0 if result.get('success') else 1)
