"""Sample only a supplied application PID and its descendants (dev: psutil)."""
import argparse
import json
from pathlib import Path
import statistics
import time

import psutil

parser = argparse.ArgumentParser()
parser.add_argument('--pid', type=int, required=True)
parser.add_argument('--seconds', type=int, default=120)
parser.add_argument('--output', required=True)
args = parser.parse_args()
root = psutil.Process(args.pid)
previous = {}
samples = []
cpu_seconds = 0
start = time.perf_counter()
last = start
for index in range(args.seconds + 1):
    rss = private = delta = 0
    for process in [root, *root.children(recursive=True)]:
        try:
            identity = (process.pid, process.create_time())
            cpu = sum(process.cpu_times()[:2])
            if index:
                delta += max(0, cpu - previous.get(identity, 0))
            previous[identity] = cpu
            info = process.memory_info()
            rss += info.rss
            private += info.private
        except psutil.NoSuchProcess:
            pass
    now = time.perf_counter()
    cpu_seconds += delta
    samples.append({'seconds': round(now-start, 2), 'private_mib': round(private/1048576, 1),
                    'working_mib': round(rss/1048576, 1),
                    'cpu_machine_percent': round(delta/max(now-last, .001)/psutil.cpu_count()*100, 3)})
    last = now
    if index < args.seconds:
        time.sleep(1)
elapsed = time.perf_counter() - start
summary = {'pid': args.pid, 'duration_seconds': round(elapsed, 2), 'logical_cpus': psutil.cpu_count(),
           'cpu_seconds': round(cpu_seconds, 3), 'mean_cpu_machine_percent': round(cpu_seconds/elapsed/psutil.cpu_count()*100, 3),
           'peak_cpu_machine_percent': max(s['cpu_machine_percent'] for s in samples),
           'median_private_mib': statistics.median(s['private_mib'] for s in samples),
           'peak_private_mib': max(s['private_mib'] for s in samples)}
Path(args.output).write_text(json.dumps({'summary': summary, 'samples': samples}, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
