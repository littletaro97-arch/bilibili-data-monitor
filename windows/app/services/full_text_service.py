"""One shared traversal worker with durable checkpoints and statistics-aligned queues."""
import asyncio
import json
import math
import time
import uuid
import hashlib

from app.database import iso_now
from app.models import ProviderError, RiskControlError, LoginRequiredError, RequestFailure, CommentUnavailableError, StaleJobError, CommentCursorError
from app.services.network_retry import network_retry_delay
from app.collectors.full_text import comment


class FullTextService:
    def __init__(self,repository,provider,auth,*,budget=150):
        self.repo=repository; self.db=repository.database; self.provider=provider; self.auth=auth
        self.budget=budget; self.task=None; self.active=None; self.lock=asyncio.Lock()
        with self.db.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS text_jobs (
                id TEXT PRIMARY KEY,bvid TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,
                state TEXT NOT NULL,message TEXT NOT NULL,updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS text_job_roots (job TEXT NOT NULL,root TEXT NOT NULL,PRIMARY KEY(job,root));
                CREATE TABLE IF NOT EXISTS text_job_cursors (job TEXT NOT NULL,cursor TEXT NOT NULL,PRIMARY KEY(job,cursor));
                CREATE TABLE IF NOT EXISTS text_job_control (key TEXT PRIMARY KEY,value REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_text_job_video ON text_jobs(bvid,kind,updated);
                CREATE INDEX IF NOT EXISTS idx_text_job_status ON text_jobs(status,updated);
                CREATE INDEX IF NOT EXISTS idx_dm_platform ON danmaku(bvid,cid,source_id);''')
            c.execute("UPDATE text_jobs SET status='paused',message='程序退出，点击继续可恢复断点' WHERE status='running'")
            # One compatibility retry for jobs stopped by the old metadata-only guard.
            c.execute("""UPDATE text_jobs SET status='queued',message='解析兼容更新后，从原分段重试',
                state=json_set(state,'$.failure_kind',NULL,'$.metadata_compat_retry',1)
                WHERE kind='danmaku' AND status='paused' AND message='弹幕分段缺少可识别字段，进度未推进'
                AND json_extract(state,'$.automatic')=1
                AND coalesce(json_extract(state,'$.manual_pause'),0)=0
                AND coalesce(json_extract(state,'$.metadata_compat_retry'),0)=0""")

            # Retry the old blocked checkpoint once; the typed endpoint result decides whether to skip.
            c.execute("""UPDATE text_jobs SET status='queued',message='从原评论断点重试',
                state=json_set(state,'$.failure_kind',NULL,'$.unavailable_compat_retry',1)
                WHERE kind='comments' AND status='paused'
                AND message='平台接口失败：code=12006；任务未完成'
                AND json_extract(state,'$.automatic')=1
                AND coalesce(json_extract(state,'$.manual_pause'),0)=0
                AND json_extract(state,'$.pending') IS NOT NULL
                AND coalesce(json_extract(state,'$.unavailable_compat_retry'),0)=0""")

            if getattr(self.auth,'is_account_pool',False) is True:
                c.execute("""UPDATE text_jobs SET state=json_set(state,'$.owner_profile','primary')
                    WHERE json_extract(state,'$.owner') IS NOT NULL AND json_extract(state,'$.owner_profile') IS NULL""")

    def load(self,identity):
        with self.db.connect() as c:
            r=c.execute('SELECT * FROM text_jobs WHERE id=?',(identity,)).fetchone()
        if not r: raise ProviderError('采集任务不存在')
        result=dict(r); result['state']=json.loads(result['state']); return result

    def latest(self,bvid):
        with self.db.connect() as c:
            r=c.execute('SELECT id FROM text_jobs WHERE bvid=? ORDER BY updated DESC,rowid DESC LIMIT 1',(bvid,)).fetchone()
        return self.public(self.load(r['id'])) if r else None

    @staticmethod
    def public(job):
        s=job['state']
        return {k:job[k] for k in ('id','bvid','kind','status','message','updated')} | {
            'responses':s.get('responses',0),'received':s.get('received',0),'saved_new':s.get('saved_new',0),
            'scope':s.get('scope'),'parts':s.get('parts',[]),'part_index':s.get('part_index',0),
            'saved_existing':max(0,s.get('received',0)-s.get('saved_new',0)-s.get('legacy_received',s.get('received',0) if job['kind']=='comments' and not s.get('counts_version') else 0)),
            'legacy_received':s.get('legacy_received',s.get('received',0) if job['kind']=='comments' and not s.get('counts_version') else 0),
            'owner_profile':s.get('owner_profile'),'handoffs':s.get('handoffs',0),'automatic':s.get('automatic',False),'failure_kind':s.get('failure_kind'),'unavailable_roots':s.get('unavailable_roots',0),
            'segment':s.get('segment',1),'retry_after':max(0,math.ceil(s.get('retry_at',0)-time.time()))}

    def assert_current(self,j):
        with self.db.connect() as c:
            row=c.execute('SELECT state FROM text_jobs WHERE id=?',(j['id'],)).fetchone()
        if row and json.loads(row['state']).get('owner_revision',0)!=j['state'].get('owner_revision',0):
            j['_stale']=True;raise StaleJobError('任务已接管，旧执行者不能继续提交')

    def save(self,j,*,expected_revision=None):
        j['updated']=iso_now()
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT state FROM text_jobs WHERE id=?',(j['id'],)).fetchone()
            expected=j['state'].get('owner_revision',0) if expected_revision is None else expected_revision
            if row and json.loads(row['state']).get('owner_revision',0)!=expected:
                j['_stale']=True;raise StaleJobError('任务已接管，旧执行者不能继续提交')
            c.execute('INSERT OR REPLACE INTO text_jobs VALUES(?,?,?,?,?,?,?)',
                (j['id'],j['bvid'],j['kind'],j['status'],json.dumps(j['state'],ensure_ascii=False),j['message'],j['updated']))
            if j['kind']=='comments' and j['state'].get('offset'):
                c.execute('INSERT OR IGNORE INTO text_job_cursors VALUES(?,?)',(j['id'],hashlib.sha256((j['state'].get('cursor_epoch','')+j['state']['offset']).encode()).hexdigest()))
            if j['state'].get('retry_at') and j['state'].get('failure_kind')=='risk':
                c.execute("INSERT OR REPLACE INTO text_job_control VALUES('retry_at',?)",(j['state']['retry_at'],))

    def latest_kind(self,bvid,kind):
        with self.db.connect() as c:
            row=c.execute('SELECT id FROM text_jobs WHERE bvid=? AND kind=? ORDER BY updated DESC,rowid DESC LIMIT 1',(bvid,kind)).fetchone()
        return self.load(row['id']) if row else None

    def jobs(self,bvid):
        return [self.public(j) for kind in ('comments','danmaku') if (j:=self.latest_kind(bvid,kind))]

    async def enqueue_tick(self,bvid):
        """No platform requests here: statistics capture must never await a full traversal."""
        if self.lock.locked():
            with self.db.connect() as c:
                c.execute('INSERT OR REPLACE INTO text_job_control VALUES(?,?)',('tick:'+bvid,time.time()))
            return
        async with self.lock:
            task=self.repo.get_task_by_bvid(bvid)
            if not task or task['status']!='running':
                with self.db.connect() as c:c.execute('DELETE FROM text_job_control WHERE key=?',('tick:'+bvid,))
                return
            for kind in ('comments','danmaku'):
                previous=self.latest_kind(bvid,kind)
                if previous and previous['status']!='complete':
                    state=previous['state']
                    if state.get('queued_manual'):continue
                    if state.get('automatic') and previous['status'] in {'queued','running','retry_wait','waiting_login'}:continue
                    if state.get('manual_pause') or state.get('failure_kind') in {'parse','provider','http','account'}:continue
                    # Legacy manual network/budget/startup pauses can resume at the same checkpoint.
                    if previous['status']=='paused' and not state.get('automatic'):
                        if state.get('pause_reason')!='video' and not previous['message'].startswith(('网络','程序退出','本轮已处理')):continue
                    state['automatic']=True
                    if previous['id']==self.active and self.task and not self.task.done():
                        self._running_job['state']['automatic']=True
                        continue
                    if previous['status']=='paused' and state.get('failure_kind')!='risk':
                        previous['status']='queued';previous['message']='下次调度从原断点继续'
                    self.save(previous);continue
                state={'automatic':True,'owner':None,'aid':None,'parts':[],'total_parts':0,
                       'scope':('selected' if task['selected_page'] else 'all') if kind=='danmaku' else 'shared','selected_page':task['selected_page'] if kind=='danmaku' else None,'part_index':0,'segment':1,
                       'offset':'','pending':None,'responses':0,'received':0,'saved_new':0,
                       'continuous':True,'counts_version':1,'scheduled_at':iso_now()}
                job={'id':uuid.uuid4().hex,'bvid':bvid,'kind':kind,'status':'queued' if self.auth.cookies else 'waiting_login',
                     'message':'随视频统计安排，等待正文通道' if self.auth.cookies else '正文等待登录，视频统计继续采集','state':state}
                self.save(job)
            with self.db.connect() as c:c.execute('DELETE FROM text_job_control WHERE key=?',('tick:'+bvid,))

    async def pump(self):
        """A small fair slice per video/channel; network waits never occupy the worker."""
        if self.lock.locked():return
        with self.db.connect() as c:
            ticks=c.execute("SELECT key FROM text_job_control WHERE key LIKE 'tick:%'").fetchall()
        for tick in ticks:await self.enqueue_tick(tick['key'][5:])
        async with self.lock:
            if self.task and not self.task.done():return
            if not self.auth.cookies or getattr(self.auth,'verification',None)=='expired':return
            try:self.check_cooldown()
            except ProviderError:return
            with self.db.connect() as c:
                rows=c.execute("""SELECT j.id FROM text_jobs j LEFT JOIN crawl_tasks t ON t.bvid=j.bvid
                    WHERE j.status IN ('queued','retry_wait','waiting_login','paused')
                    AND ((json_extract(j.state,'$.automatic')=1 AND t.status='running')
                        OR (json_extract(j.state,'$.queued_manual')=1 AND coalesce(t.status,'')!='stopped'))
                    AND coalesce(json_extract(j.state,'$.manual_pause'),0)=0
                    AND coalesce(json_extract(j.state,'$.failure_kind'),'') NOT IN ('parse','provider','http','account')
                    AND coalesce(json_extract(j.state,'$.retry_at'),0)<=?
                    ORDER BY j.updated,j.rowid LIMIT 1""",(time.time(),)).fetchall()
            for row in rows:
                job=self.load(row['id']);state=job['state'];task=self.repo.get_task_by_bvid(job['bvid'])
                if state.get('manual_pause') or state.get('failure_kind') in {'parse','provider','http','account'}:continue
                if not state.get('queued_manual') and (not task or task['status']!='running'):continue
                if job['status']=='paused' and state.get('failure_kind') not in {None,'risk','network','timeout'}:continue
                job['status']='running';job['message']='正在从断点继续';self.save(job);self.launch(job);break

    async def prepare_auto(self,j):
        s=j['state']
        if not self.auth.cookies:raise LoginRequiredError('请先登录后采集正文')
        verified=getattr(self.auth,'last_verified_at',None)
        from app.database import parse_iso,local_now
        recent=parse_iso(verified) if verified else None
        if not s.get('aid') or getattr(self.auth,'verification',None)!='valid' or not recent or (local_now()-recent).total_seconds()>300:
            await self.auth.validate()
        if s.get('owner') and s['owner']!=self.auth.account:
            raise RequestFailure('account','登录账户已改变，请手动确认或新建正文任务')
        s['owner']=self.auth.account
        if not s.get('aid') or not s.get('parts'):
            aid,parts=await self.provider.view(j['bvid']);s['aid']=aid;s['total_parts']=len(parts)
            if j['kind']=='danmaku' and s.get('selected_page'):
                parts=[p for p in parts if p['page']==s['selected_page']]
                if not parts:raise ProviderError('链接指定的分 P 不存在，正文任务已暂停')
            s['parts']=parts
        self.save(j)

    def save_comments(self,j,rows):
        self.assert_current(j)
        s=j['state'];ids={(r.bvid,r.rpid) for r in rows}
        if not s.get('counts_version'):
            s['legacy_received']=s.get('received',0);s['counts_version']=1
        with self.db.connect() as c:
            existing=sum(bool(c.execute('SELECT 1 FROM comments WHERE bvid=? AND rpid=?',identity).fetchone()) for identity in ids)
        self.repo.insert_comments(rows)
        s['received']+=len(rows);s['saved_new']+=len(ids)-existing

    def idle(self):
        if self.task and not self.task.done(): raise ProviderError('已有文本采集正在运行，请先暂停')

    def check_cooldown(self):
        with self.db.connect() as c:
            r=c.execute("SELECT value FROM text_job_control WHERE key='retry_at'").fetchone()
        if r and r['value']>time.time(): raise ProviderError('登录采集处于平台限制冷却中，请稍后继续')

    def ensure_video(self,bvid):
        if not self.repo.get_video(bvid): raise ProviderError('请先添加视频任务')
        task=self.repo.get_task_by_bvid(bvid)
        if task and task['status']=='stopped': raise ProviderError('链接在回收站中，请先取回后采集')

    async def start(self,bvid,kind,scope,cid,*,continuous=False):
        async with self.lock:
            self.check_cooldown()
            if kind not in {'comments','danmaku'} or scope not in {'selected','all'}: raise ProviderError('采集参数不正确')
            self.ensure_video(bvid)
            previous=self.latest_kind(bvid,kind)
            if previous and previous['status']!='complete':
                raise ProviderError('已有未完成的同类正文任务，请从断点继续，避免重复遍历')
            if not self.auth.cookies: raise ProviderError('请先在设置中登录 Bilibili')
            await self.auth.validate()
            aid,parts=await self.provider.view(bvid)
            task=self.repo.get_task_by_bvid(bvid)
            page=task['selected_page'] if task else None
            selected=parts if kind=='comments' or scope=='all' else [p for p in parts if p['cid']==cid]
            if kind=='danmaku' and page:
                selected=[p for p in parts if p['page']==page];scope='selected'
            if not selected: raise ProviderError('所选 P 不属于该视频，请先读取分 P 列表')
            j={'id':uuid.uuid4().hex,'bvid':bvid,'kind':kind,'status':'running','message':'正在采集',
                'state':{'owner':self.auth.account,'aid':aid,'parts':selected,'total_parts':len(parts),
                    'scope':'shared' if kind=='comments' else scope,'part_index':0,'segment':1,
                    'offset':'','pending':None,'responses':0,'received':0,'saved_new':0,'continuous':bool(continuous),'counts_version':1}}
            if getattr(self.auth,'is_account_pool',False) is True:j['state']['owner_profile']=self.auth.current_key()
            self.save(j)
            self.repo.record_text_collection(bvid,kind,{'parts':selected,'total_parts':len(parts),'scope':scope,
                'authenticated':True,'complete':False,'interrupted':True,'job':j['id']})
            self.dispatch_manual(j); return self.public(j)

    def dispatch_manual(self,j):
        if self.task and not self.task.done():
            j['state']['queued_manual']=True
            j['status']='queued';j['message']='等待正文通道空闲后从断点采集'
            self.save(j)
        else:self.launch(j)

    def launch(self,j):
        if j['state'].pop('queued_manual',False):
            j['state']['verify_dispatch']=True;self.save(j)
        self.active=j['id']; self._running_job=j
        if not j['state'].get('automatic'):self.provider.keys=None
        self.task=asyncio.create_task(self.run(j))

    async def resume(self,identity,*,continuous=False):
        async with self.lock:
            self.check_cooldown(); j=self.load(identity)
            if self.task and not self.task.done() and identity==self.active:
                return self.public(self._running_job)
            if j['status']=='queued' and j['state'].get('queued_manual'):
                return self.public(j)
            self.ensure_video(j['bvid'])
            if j['status']=='complete': raise ProviderError('接口遍历已经结束，可新建任务刷新')
            if j['state'].get('retry_at',0)>time.time(): raise ProviderError('平台限制冷却中，请稍后继续')
            if not self.auth.cookies: raise ProviderError('请先登录')
            await self.auth.validate()
            if getattr(self.auth,'is_account_pool',False) is not True and j['state'].get('owner') and j['state']['owner']!=self.auth.account: raise ProviderError('请使用创建该任务的 Bilibili 账户继续')
            if getattr(self.auth,'is_account_pool',False) is True:j['state']['allow_account_rebind']=True
            if continuous:j['state']['continuous']=True
            j['state'].pop('manual_pause',None); j['state']['failure_kind']=None; j['state']['retry_at']=0
            j['status']='running'; j['message']='从断点继续'; self.save(j); self.dispatch_manual(j); return self.public(j)

    async def cancel(self,identity=None,*,shutdown=False):
        async with self.lock:
            if self.task and not self.task.done() and (identity is None or identity==self.active):
                self._shutdown_cancel=shutdown
                self.task.cancel()
                await self.task
            elif identity:
                job=self.load(identity)
                if job['status']!='complete':
                    job['status']='paused';job['message']='已手动暂停';job['state']['manual_pause']=True;self.save(job)

    async def cancel_video(self,bvid):
        if self.active and self.load(self.active)['bvid']==bvid:
            await self.cancel(self.active)
            job=self.load(self.active);job['state'].pop('manual_pause',None);job['state']['pause_reason']='video';self.save(job)

    def save_dm(self,items):
        with self.db.connect() as c:
            before=c.total_changes
            for r in items:
                c.execute('''INSERT INTO danmaku(bvid,cid,progress_sec,text,send_time,captured_at,raw_text,source_id,visibility,visibility_checked_at)
                    SELECT ?,?,?,?,?,?,NULL,?,'observed',? WHERE NOT EXISTS (
                    SELECT 1 FROM danmaku WHERE bvid=? AND cid=? AND source_id=?)''',
                    (r.bvid,r.cid,r.progress_sec,r.text,r.send_time,iso_now(),r.source_id,iso_now(),r.bvid,r.cid,r.source_id))
            added=c.total_changes-before
            for r in items:c.execute("UPDATE danmaku SET visibility='observed',visibility_checked_at=? WHERE bvid=? AND cid=? AND source_id=?",(iso_now(),r.bvid,r.cid,r.source_id))
            return added

    async def dm_step(self,j):
        s=j['state']; parts=s['parts']
        if s['part_index']>=len(parts): return True
        p=parts[s['part_index']]; count=max(1,math.ceil(p['duration']/360))
        if count>10000: raise ProviderError('视频时长异常，无法计算分段范围')
        rows=await self.provider.segment(j['bvid'],p['cid'],s['segment'])
        self.assert_current(j)
        s['saved_new']+=self.save_dm(rows); s['received']+=len(rows)
        s['segment']+=1
        if s['segment']>count: s['part_index']+=1; s['segment']=1
        return s['part_index']>=len(parts)

    def root_done(self,job,root,*,mark=False):
        with self.db.connect() as c:
            if mark: c.execute('INSERT OR IGNORE INTO text_job_roots VALUES(?,?)',(job,root))
            return bool(c.execute('SELECT 1 FROM text_job_roots WHERE job=? AND root=?',(job,root)).fetchone())

    async def comments_step(self,j):
        s=j['state']; pending=s['pending']; bvid=j['bvid']
        if pending is None:
            d=await self.provider.roots(s['aid'],s['offset']); cursor=d.get('cursor') or {}
            if not isinstance(cursor.get('is_end'),bool): raise ProviderError('评论游标缺少结束标记，任务未完成')
            roots=d.get('replies') or []
            for r in (d.get('top_replies') or []): roots.append(r)
            if len(roots)>100: raise ProviderError('单页评论过多，任务已暂停')
            unique={comment(r,bvid).rpid:r for r in roots}
            self.save_comments(j,[comment(r,bvid) for r in roots])
            end=cursor['is_end']; next_offset=(cursor.get('pagination_reply') or {}).get('next_offset')
            if not end and (not isinstance(next_offset,str) or not next_offset or next_offset==s['offset']):
                raise ProviderError('评论游标未前进，已保存本页，任务未完成')
            if not end:
                digest=hashlib.sha256((s.get('cursor_epoch','')+next_offset).encode()).hexdigest()
                with self.db.connect() as c:
                    if c.execute('SELECT 1 FROM text_job_cursors WHERE job=? AND cursor=?',(j['id'],digest)).fetchone():
                        raise ProviderError('评论游标形成循环，任务未完成')
            pending={'roots':[{'id':k,'count':int(r.get('rcount') or 0)} for k,r in unique.items()],
                'index':0,'page':1,'next':next_offset,'end':end}
            s['pending']=pending
        else:
            roots=pending['roots']
            while pending['index']<len(roots):
                root=roots[pending['index']]
                if not root['count'] or self.root_done(j['id'],root['id']):
                    pending['index']+=1; pending['page']=1; continue
                try:
                    d=await self.provider.children(s['aid'],root['id'],pending['page'])
                except CommentUnavailableError:
                    self.assert_current(j)
                    # An explicit missing-root response is not proof of deletion. Preserve all text.
                    with self.db.connect() as c:
                        c.execute("UPDATE comments SET visibility='unavailable',visibility_checked_at=? WHERE bvid=? AND rpid=?",
                                  (iso_now(),bvid,root['id']))
                    self.root_done(j['id'],root['id'],mark=True)
                    s['unavailable_roots']=s.get('unavailable_roots',0)+1
                    pending['index']+=1;pending['page']=1
                    break
                self.assert_current(j)
                page=d.get('page') or {}; rows=d.get('replies') or []
                if len(rows)>100: raise ProviderError('楼中楼单页过多，任务已暂停')
                if 'count' not in page or int(page.get('num',0))!=pending['page'] or int(page.get('size',0))<=0:
                    raise ProviderError('楼中楼分页信息异常，任务未完成')
                count=int(page['count']); size=int(page['size'])
                end=pending['page']*size>=count
                if not rows and count>0: raise ProviderError('楼中楼返回空页但仍有计数，任务未完成')
                # True parent is retained when supplied; root is the fallback.
                parsed=[comment(r,bvid,str(r.get('parent_str') or r.get('parent') or root['id'])) for r in rows]
                self.save_comments(j,parsed)
                if end:
                    self.root_done(j['id'],root['id'],mark=True); pending['index']+=1; pending['page']=1
                else: pending['page']+=1
                break
        while pending['index']<len(pending['roots']):
            root=pending['roots'][pending['index']]
            if root['count'] and not self.root_done(j['id'],root['id']):break
            pending['index']+=1;pending['page']=1
        if pending['index']>=len(pending['roots']):
            s['offset']=pending['next'] or ''; s['pending']=None
            return pending['end']
        return False

    async def run(self,j):
        token=None
        automatic=j['state'].get('automatic',False)
        try:
            if getattr(self.auth,'is_account_pool',False) is True:
                state=j['state'];old_owner=state.get('owner');old_revision=state.get('owner_revision',0)
                preferred=state.get('owner_profile') or (self.auth.preferred(j['bvid']) if not old_owner else None)
                key=await self.auth.choose(old_owner,preferred,allow_rebind=state.pop('allow_account_rebind',False))
                token=self.auth.bind(key)
                if old_owner and (old_owner!=self.auth.account or (state.get('owner_profile') and state['owner_profile']!=key)):
                    state.setdefault('created_owner',old_owner)
                    state['owner_revision']=old_revision+1;state['handoff_pending']=True;state['handoffs']=state.get('handoffs',0)+1
                    self.provider.keys=None
                    state['owner']=self.auth.account;state['owner_profile']=key
                    self.save(j,expected_revision=old_revision)
                    self.repo.add_log('INFO','正文任务已切换可用账号，原断点保留',bvid=j['bvid'],detail=f"job={j['id']} profile={key}")
                else:
                    state['owner']=self.auth.account;state['owner_profile']=key;self.save(j)
            verify_dispatch=j['state'].pop('verify_dispatch',False)
            if automatic or verify_dispatch:await self.prepare_auto(j)
            # Automatic work continues in four-response slices; explicit manual traversal stays bounded.
            limit=4 if automatic else (self.budget*40 if j['state'].get('continuous') else self.budget)
            for _ in range(limit):
                self.ensure_video(j['bvid'])
                task=self.repo.get_task_by_bvid(j['bvid'])
                if automatic and (not task or task['status']!='running'):
                    j['status']='queued';j['message']='视频检测已暂停，正文断点保留';break
                complete=j['state'].get('traversed',False)
                if not complete:
                    complete=await (self.dm_step(j) if j['kind']=='danmaku' else self.comments_step(j))
                    j['state']['responses']+=1
                j['state']['handoff_pending']=False
                j['state']['traversed']=complete
                j['state']['network_failures']=0;j['state']['retry_at']=0;j['state']['failure_kind']=None
                j['message']='正在逐段读取' if j['kind']=='danmaku' else '正在读取评论及楼中楼'
                self.save(j)
                if complete:
                    j['status']='complete'; j['message']='接口遍历结束；已保存原文留存，不保证完整历史'
                    self.repo.record_text_collection(j['bvid'],j['kind'],{**{k:j['state'][k] for k in ('parts','total_parts','scope','received','responses','saved_new')},
                        'authenticated':True,'complete':False,'traversal_complete':True,'interrupted':False,'job':j['id']})
                    break
                if j['state'].get('automatic') and _>=3:
                    j['status']='queued';j['message']='分批保存后继续同一断点';break
                await asyncio.sleep(0)
            else:
                j['status']='queued' if automatic else 'paused'
                j['message']='本轮分批保存，继续同一断点' if automatic else f'本轮已处理 {limit} 个批次，点击继续读取后续数据'
        except StaleJobError:
            j['_stale']=True
        except asyncio.CancelledError:
            account_exit=getattr(self,'_account_exit_cancel',False);self._account_exit_cancel=False
            interrupted=getattr(self,'_shutdown_cancel',False);self._shutdown_cancel=False
            j['status']='queued' if automatic and interrupted else 'paused'
            j['state']['manual_pause']=not interrupted and not account_exit
            if account_exit:
                j['status']='waiting_login';j['state']['failure_kind']='login'
                if not automatic:j['state']['queued_manual']=True
            j['message']='账号退出，断点等待可用账号接管' if account_exit else ('程序退出，正文断点已保留' if interrupted else '已暂停，已保存的数据和断点保留')
        except LoginRequiredError as exc:
            if getattr(self.auth,'is_account_pool',False) is True and token is not None:
                try:await self.auth.expired(exc)
                except RequestFailure as denied:
                    j['status']='paused';j['state']['failure_kind']=denied.kind;j['message']=str(denied)
                    if denied.kind in {'network','timeout'}:
                        failures=j['state'].get('network_failures',0)+1;j['state']['network_failures']=failures
                        j['status']='retry_wait';j['state']['automatic']=True;j['state']['retry_at']=time.time()+network_retry_delay(failures)
                except RiskControlError:
                    self.provider.keys=None;j['status']='paused';j['state']['failure_kind']='risk';j['state']['retry_at']=time.time()+max(600,self.auth.cooldown_seconds if getattr(self.auth,'is_account_pool',False) is True else 600)
                    j['message']='平台限制，共享通道冷却，断点保留'
                else:
                    j['status']='waiting_login';j['state']['failure_kind']='login';j['state']['retry_at']=0
                    j['message']='该账号登录失效，断点保留；有备用账号时自动接管'
                    if not automatic:j['state']['queued_manual']=True
            else:
                j['status']='waiting_login';j['state']['failure_kind']='login';j['state']['retry_at']=0;j['message']='登录已失效或未登录，断点保留，重新登录后继续'
                if getattr(self.auth,'is_account_pool',False) is True and not automatic:j['state']['queued_manual']=True
        except RiskControlError:
            self.provider.keys=None
            j['status']='paused';j['state']['failure_kind']='risk';j['state']['retry_at']=time.time()+max(600,self.auth.cooldown_seconds if getattr(self.auth,'is_account_pool',False) is True else 600)
            j['message']='平台明确限制请求，共享通道冷却，断点保留'
        except RequestFailure as exc:
            kind=exc.kind;j['state']['failure_kind']=kind
            if kind in {'timeout','network'}:
                failures=j['state'].get('network_failures',0)+1;j['state']['network_failures']=failures
                delay=network_retry_delay(failures);j['state']['retry_at']=time.time()+delay
                j['status']='retry_wait';j['state']['automatic']=True
                j['message']=f'{str(exc)}；{delay} 秒后从断点重试（超时不能直接判定限流）'
            else:j['status']='paused';j['message']=str(exc)
        except CommentCursorError as exc:
            state=j['state'];revision=state.get('owner_revision',0)
            if j['kind']=='comments' and state.get('handoff_pending') and state.get('offset') and state.get('pending') is None and state.get('cursor_fallback_revision')!=revision:
                state['offset']='';state['cursor_epoch']=f'handoff-{revision}:';state['cursor_fallback_revision']=revision
                state['failure_kind']=None;state['handoff_pending']=False;j['status']='queued'
                if not automatic:state['queued_manual']=True
                j['message']='备用账号不能复用旧游标，保留原文，从首页去重续查'
            else:j['status']='paused';state['failure_kind']='provider';j['message']=str(exc)
        except ProviderError as exc:
            j['status']='paused';j['state']['failure_kind']='provider';j['message']=str(exc)
        except Exception:
            j['status']='paused';j['state']['failure_kind']='parse'
            j['message']='响应结构或本地保存异常，进度已保留，请检查后继续'
        finally:
            if token is not None:self.auth.unbind(token)
            if j.get('_stale'):return
            try:self.save(j)
            except StaleJobError:return
            state=j['state']
            self.repo.add_log('INFO' if j['status'] in {'complete','queued'} else 'WARNING','正文采集批次结束',bvid=j['bvid'],
                detail=f"{j['kind']} job={j['id']} status={j['status']} responses={state.get('responses',0)} received={state.get('received',0)} new={state.get('saved_new',0)} existing={self.public(j)['saved_existing']} unavailable_roots={state.get('unavailable_roots',0)} failure={state.get('failure_kind') or '-'}")

    async def account_exit(self,profile):
        if self.task and not self.task.done() and self._running_job['state'].get('owner_profile','primary')==profile:
            self._account_exit_cancel=True
            await self.cancel(self.active)

    async def shutdown(self):
        await self.cancel(shutdown=True)
