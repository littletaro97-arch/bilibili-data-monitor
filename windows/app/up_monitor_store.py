"""Persistent discovery checkpoints; queue overflow never advances away unsaved videos."""
from datetime import timedelta
from app.database import iso_now, local_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS up_monitors (
 id INTEGER PRIMARY KEY, mid INTEGER NOT NULL UNIQUE, up_name TEXT NOT NULL,
 baseline_pubdate INTEGER NOT NULL, interval_seconds INTEGER NOT NULL,
 video_interval_seconds INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'running',
 next_run_at TEXT NOT NULL, cooldown_until TEXT, last_checked_at TEXT, last_error TEXT,
 consecutive_failures INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS up_monitor_videos (
 monitor_id INTEGER NOT NULL, bvid TEXT NOT NULL, title TEXT NOT NULL, pubdate INTEGER NOT NULL,
 state TEXT NOT NULL, promoted INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(monitor_id,bvid)
);
CREATE TABLE IF NOT EXISTS up_monitor_preferences (
 id INTEGER PRIMARY KEY CHECK(id=1), detect_interval INTEGER NOT NULL, video_interval INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS html_reports (
 filename TEXT PRIMARY KEY, bvid TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL
);
"""

class UpMonitorStore:
    def __init__(self, repo): self.repo=repo
    def get(self, identity):
        with self.repo.database.connect() as c:return c.execute('SELECT * FROM up_monitors WHERE id=?',(identity,)).fetchone()
    def list(self):
        with self.repo.database.connect() as c:return c.execute('SELECT * FROM up_monitors ORDER BY created_at DESC,id DESC').fetchall()
    def defaults(self, video_interval):
        with self.repo.database.connect() as c:
            r=c.execute('SELECT * FROM up_monitor_preferences WHERE id=1').fetchone()
            return (r['detect_interval'],r['video_interval']) if r else (300,video_interval)
    def add(self,mid,name,rows,interval,video_interval):
        stamp=iso_now();baseline=max((r['pubdate'] for r in rows),default=int(local_now().timestamp()))
        with self.repo.database.connect() as c:
            identity=c.execute('INSERT INTO up_monitors(mid,up_name,baseline_pubdate,interval_seconds,video_interval_seconds,next_run_at,last_checked_at,created_at) VALUES (?,?,?,?,?,?,?,?)',
                (mid,name,baseline,interval,video_interval,(local_now()+timedelta(seconds=interval)).isoformat(),stamp,stamp)).lastrowid
            c.executemany("INSERT INTO up_monitor_videos(monitor_id,bvid,title,pubdate,state) VALUES (?,?,?,?,'baseline')",[(identity,r['bvid'],r['title'],r['pubdate']) for r in rows])
            c.execute('INSERT OR REPLACE INTO up_monitor_preferences VALUES (1,?,?)',(interval,video_interval))
            return identity
    def discover(self,identity,rows):
        with self.repo.database.connect() as c:
            monitor=c.execute('SELECT * FROM up_monitors WHERE id=?',(identity,)).fetchone()
            if not monitor or monitor['status']!='running':return
            for r in rows:
                if r['pubdate']>=monitor['baseline_pubdate']:
                    c.execute("INSERT OR IGNORE INTO up_monitor_videos(monitor_id,bvid,title,pubdate,state) VALUES (?,?,?,?,'pending')",(identity,r['bvid'],r['title'],r['pubdate']))
            baseline=max([monitor['baseline_pubdate']]+[r['pubdate'] for r in rows])
            c.execute('UPDATE up_monitors SET baseline_pubdate=?,last_checked_at=?,next_run_at=?,last_error=NULL,cooldown_until=NULL,consecutive_failures=0 WHERE id=?',
                (baseline,iso_now(),(local_now()+timedelta(seconds=monitor['interval_seconds'])).isoformat(),identity))
    def pending(self,identity):
        with self.repo.database.connect() as c:return c.execute("SELECT * FROM up_monitor_videos WHERE monitor_id=? AND state='pending' ORDER BY pubdate,bvid",(identity,)).fetchall()
    def queued(self,identity,bvid,existing=False):
        with self.repo.database.connect() as c:c.execute("UPDATE up_monitor_videos SET state='queued',promoted=? WHERE monitor_id=? AND bvid=?",(int(existing),identity,bvid))
    def items(self):
        with self.repo.database.connect() as c:return c.execute("SELECT * FROM up_monitor_videos WHERE state!='baseline'").fetchall()
    def state(self,identity,status):
        with self.repo.database.connect() as c:c.execute('UPDATE up_monitors SET status=? WHERE id=?',(status,identity))
    def fail(self,identity,message,seconds):
        with self.repo.database.connect() as c:c.execute('UPDATE up_monitors SET last_error=?,last_checked_at=?,cooldown_until=?,consecutive_failures=consecutive_failures+1 WHERE id=?',
            (message,iso_now(),(local_now()+timedelta(seconds=seconds)).isoformat(),identity))
    def require_login(self):
        with self.repo.database.connect() as c:c.execute("UPDATE up_monitors SET status='needs_login',last_error='请在设置中重新扫码，然后恢复 UP 检测' WHERE status='running'")
    def remove(self,identity):
        with self.repo.database.connect() as c:
            c.execute('DELETE FROM up_monitor_videos WHERE monitor_id=?',(identity,));c.execute('DELETE FROM up_monitors WHERE id=?',(identity,))
    def promote(self,identity,bvid):
        with self.repo.database.connect() as c:c.execute("UPDATE up_monitor_videos SET promoted=1 WHERE monitor_id=? AND bvid=? AND state='queued'",(identity,bvid))
    def intervals(self,identity,interval,video_interval):
        with self.repo.database.connect() as c:c.execute('UPDATE up_monitors SET interval_seconds=?,video_interval_seconds=?,next_run_at=? WHERE id=?',(interval,video_interval,(local_now()+timedelta(seconds=interval)).isoformat(),identity))

    def cooldown_all(self,message,seconds):
        with self.repo.database.connect() as c:c.execute("UPDATE up_monitors SET cooldown_until=?,last_error=? WHERE status='running'",((local_now()+timedelta(seconds=seconds)).isoformat(),message))
