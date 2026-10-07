"""New-video discovery is separate from the existing statistics task scheduler."""
import asyncio
import re
import sqlite3
from urllib.parse import urlsplit
from app.collectors.video_info import resolve_bvid
from app.database import local_now,parse_iso
from app.models import AppError,ProviderError,RateLimitError,RiskControlError,LoginRequiredError
from app.up_monitor_store import UpMonitorStore

class UpMonitorService:
    def __init__(self,repo,provider,video_service,crawl_service,risk_seconds=3600,failure_seconds=300):
        self.repo=repo;self.store=UpMonitorStore(repo);self.provider=provider
        self.video_service=video_service;self.crawl_service=crawl_service
        self.risk_seconds=risk_seconds;self.failure_seconds=failure_seconds;self.inflight=set()

    def validate_intervals(self,interval,video_interval):
        if not 120<=interval<=31536000:raise RateLimitError('UP 检测间隔须为 120 至 31536000 秒')
        if not self.video_service.min_interval<=video_interval<=31536000:raise RateLimitError(f'视频采集间隔最低 {self.video_service.min_interval} 秒')

    async def resolve_mid(self,text):
        text=text.strip()
        if len(text)>2048:raise ProviderError("UP 输入内容过长")
        if text.isdigit():mid=int(text)
        else:
            try:url=urlsplit(text);port=url.port
            except ValueError:raise ProviderError('UP 链接格式不正确') from None
            if url.scheme in {'https','http'} and url.hostname=='space.bilibili.com' and not url.username and port in {None,80,443}:
                part=url.path.strip('/').split('/')[0]
                if not part.isdigit():raise ProviderError('请填写 UP 数字 UID 或空间链接')
                mid=int(part)
            else:
                bvid=await resolve_bvid(text);info=await self.video_service.provider.fetch_video_info(bvid)
                mid=info.owner_mid or 0
        if not 0<mid<2**63:raise ProviderError('UP 数字 UID 不正确')
        return mid

    async def add(self,text,interval,video_interval):
        self.validate_intervals(interval,video_interval)
        if len(self.store.list())>=20:raise RateLimitError('最多监控 20 位 UP 主')
        mid=await self.resolve_mid(text)
        if any(m['mid']==mid for m in self.store.list()):raise ProviderError('该 UP 已在检测列表中')
        rows,total=await self.provider.page(mid)
        name=next((r['author'] for r in rows if r.get('author') and r.get('owner_mid',mid)==mid),f'UP {mid}')
        try:identity=self.store.add(mid,name,rows,interval,video_interval)
        except sqlite3.IntegrityError:raise ProviderError('该 UP 已在检测列表中') from None
        self.repo.add_log('INFO','UP 检测已建立基线，不补录旧视频',detail=f'UID {mid}')
        return identity

    async def poll(self,identity):
        monitor=self.store.get(identity)
        if not monitor:return {'skipped':'UP 检测不存在'}
        if monitor['status']!='running':return {'skipped':'UP 检测已暂停或需要重新登录'}
        if identity in self.inflight:return {'skipped':'UP 正在检测，请等待本轮完成'}
        cooldown=parse_iso(monitor['cooldown_until'])
        if cooldown and cooldown>local_now():return {"skipped":f"UP 处于冷却中，将于 {cooldown.strftime('%H:%M:%S')} 自动重试"}
        self.inflight.add(identity)
        try:
            rows=[]
            for page in range(1,11):
                current,total=await self.provider.page(monitor['mid'],page)
                rows.extend(current)
                if page*30>=total or (current and max(r['pubdate'] for r in current)<monitor['baseline_pubdate']):break
            else:raise ProviderError('新稿列表超过本轮 300 条安全范围，基线未推进')
            self.store.discover(identity,rows)
            if self.store.get(identity) is None:return
            await self.enqueue_pending(identity)
        except LoginRequiredError:
            self.store.require_login();self.repo.add_log('WARNING','UP 检测因登录失效暂停，请重新扫码并恢复')
        except RiskControlError as exc:
            if hasattr(self.provider,"keys"): self.provider.keys=None
            self.store.fail(identity,str(exc),self.risk_seconds,"risk")
            self.store.cooldown_all("平台限制，共享 UP 请求通道冷却",self.risk_seconds)
            self.repo.add_log('WARNING','UP 检测触发平台限制，停止本轮并冷却',detail=f'UID {monitor["mid"]}')
        except AppError as exc:
            self.store.fail(identity,str(exc),self.failure_seconds,getattr(exc,"kind","provider"))
            self.repo.add_log('WARNING','UP 检测未完成，待加入项和基线保留',detail=str(exc))
        except Exception:
            self.store.fail(identity,"UP 检测出现异常，已延后重试",self.failure_seconds)
            self.repo.add_log("ERROR","UP 检测出现异常，断点保留")
        finally:self.inflight.discard(identity)
        current=self.store.get(identity)
        return {"error":current["last_error"]} if current and current["last_error"] else {"success":True}

    async def enqueue_pending(self,identity):
        for row in self.store.pending(identity):
            monitor=self.store.get(identity)
            if not monitor or monitor['status']!='running':return
            existing=self.repo.get_task_by_bvid(row['bvid'])
            if existing:
                # Never revive a user's recycled task or alter manual settings.
                self.store.queued(identity,row['bvid'],existing=True);continue
            if self.repo.count_active_tasks()>=self.video_service.max_active_tasks:
                self.store.fail(identity,'视频队列已满，新稿保留待加入',monitor['interval_seconds']);return
            await self.video_service.add_video_task(row['bvid'],monitor['video_interval_seconds'],
                should_add=lambda: bool((m:=self.store.get(identity)) and m["status"]=="running"))
            if not self.store.get(identity):return
            self.store.queued(identity,row['bvid'])
            await self.crawl_service.collect_once(row['bvid'],collection_source='UP_MONITOR')

    async def run_due(self):
        for m in self.store.list():
            if m['status']=='running' and parse_iso(m['next_run_at'])<=local_now():await self.poll(m['id'])

    def layout(self,tasks):
        grouped={}
        for m in self.store.list():
            status={'running':'正常','paused':'停止','needs_login':'待登录'}.get(m['status'],'异常')
            if m['status']=='running' and parse_iso(m['cooldown_until']) and parse_iso(m['cooldown_until'])>local_now(): status='中断'
            grouped[m['id']]={'monitor':m,'display':status,'tasks':[],'pending':[]}
        by_bvid={t['bvid']:t for t in tasks};hidden=set()
        for row in self.store.items():
            if row['monitor_id'] not in grouped:continue
            if row['state']=='pending':grouped[row['monitor_id']]['pending'].append(row)
            elif not row['promoted'] and row['bvid'] in by_bvid:
                grouped[row['monitor_id']]['tasks'].append(by_bvid[row['bvid']]);hidden.add(row['bvid'])
        return [t for t in tasks if t['bvid'] not in hidden],list(grouped.values())

    def state_snapshot(self):
        import hashlib,json
        monitors=self.store.list();items=self.store.items()
        state=[[(m['id'],m['status'],m['last_error'],m['interval_seconds'],m['video_interval_seconds'],
                 bool(parse_iso(m['cooldown_until']) and parse_iso(m['cooldown_until'])>local_now())) for m in monitors],
               [(r['monitor_id'],r['bvid'],r['state'],r['promoted']) for r in items]]
        return {'revision':hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest(),
                'checked':{str(m['id']):m['last_checked_at'] for m in monitors}}
