"""Schedule batch recovery without blocking the panel on platform requests."""
import asyncio
from app.database import local_now,iso_now,parse_iso

class RecoveryService:
    def __init__(self,repo,crawl,up,auth):
        self.repo=repo;self.crawl=crawl;self.up=up;self.auth=auth;self.lock=asyncio.Lock()

    async def run(self):
        if self.lock.locked():return {'skipped':'一键重启检测正在进行，请等待完成'}
        async with self.lock:
            result={'videos':0,'ups':0,'skipped':0,'failed':0}
            for task in self.repo.list_tasks(include_stopped=True):
                if task['status'] in {'paused','stopped'} or task['bvid'] in self.crawl._inflight:
                    result['skipped']+=1;continue
                until=parse_iso(task['cooldown_until'])
                if until and until>local_now() and task['failure_kind'] not in {'network','timeout'}:
                    result['skipped']+=1;continue
                if task['status']!='running' and self.repo.count_active_tasks()>=self.up.video_service.max_active_tasks:
                    result['skipped']+=1;continue
                with self.repo.database.connect() as c:
                    c.execute("UPDATE crawl_tasks SET status='running',cooldown_until=NULL,last_error=NULL,failure_kind=NULL,consecutive_failures=0,next_run_at=? WHERE id=? AND status NOT IN ('paused','stopped')",(iso_now(),task['id']))
                result['videos']+=1
            status=self.auth.status();verified=parse_iso(status.get('last_verified_at'))
            login_ok=bool(status.get('saved') and status.get('verification')=='valid' and verified and (local_now()-verified).total_seconds()<300)
            for previous in self.up.store.list():
                m=self.up.store.get(previous['id'])
                if not m or m['status']=='paused' or m['id'] in self.up.inflight or (m['status']=='needs_login' and not login_ok):
                    result['skipped']+=1;continue
                until=parse_iso(m['cooldown_until'])
                if until and until>local_now() and m['failure_kind'] not in {'network','timeout'}:
                    result['skipped']+=1;continue
                with self.repo.database.connect() as c:
                    c.execute("UPDATE up_monitors SET status='running',cooldown_until=NULL,last_error=NULL,failure_kind=NULL,consecutive_failures=0,next_run_at=? WHERE id=? AND status!='paused'",(iso_now(),m['id']))
                result['ups']+=1
            self.repo.add_log('INFO','一键重启检测已安排',detail=str(result))
            return result
