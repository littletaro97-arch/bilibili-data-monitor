"""One manual traversal at a time, with durable per-response checkpoints."""
import asyncio
import json
import math
import time
import uuid
import hashlib

from app.database import iso_now
from app.models import ProviderError, RiskControlError
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
                CREATE INDEX IF NOT EXISTS idx_dm_platform ON danmaku(bvid,cid,source_id);''')
            c.execute("UPDATE text_jobs SET status='paused',message='程序退出，点击继续可恢复断点' WHERE status='running'")

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
            'segment':s.get('segment',1),'retry_after':max(0,math.ceil(s.get('retry_at',0)-time.time()))}

    def save(self,j):
        j['updated']=iso_now()
        with self.db.connect() as c:
            c.execute('INSERT OR REPLACE INTO text_jobs VALUES(?,?,?,?,?,?,?)',
                (j['id'],j['bvid'],j['kind'],j['status'],json.dumps(j['state'],ensure_ascii=False),j['message'],j['updated']))
            if j['kind']=='comments' and j['state'].get('offset'):
                c.execute('INSERT OR IGNORE INTO text_job_cursors VALUES(?,?)',(j['id'],hashlib.sha256(j['state']['offset'].encode()).hexdigest()))
            if j['state'].get('retry_at'):
                c.execute("INSERT OR REPLACE INTO text_job_control VALUES('retry_at',?)",(j['state']['retry_at'],))

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

    async def start(self,bvid,kind,scope,cid):
        async with self.lock:
            self.idle()
            self.check_cooldown()
            if kind not in {'comments','danmaku'} or scope not in {'selected','all'}: raise ProviderError('采集参数不正确')
            self.ensure_video(bvid)
            if not self.auth.cookies: raise ProviderError('请先在设置中登录 Bilibili')
            await self.auth.validate()
            aid,parts=await self.provider.view(bvid)
            selected=parts if kind=='comments' or scope=='all' else [p for p in parts if p['cid']==cid]
            if not selected: raise ProviderError('所选 P 不属于该视频，请先读取分 P 列表')
            j={'id':uuid.uuid4().hex,'bvid':bvid,'kind':kind,'status':'running','message':'正在采集',
                'state':{'owner':self.auth.account,'aid':aid,'parts':selected,'total_parts':len(parts),
                    'scope':'shared' if kind=='comments' else scope,'part_index':0,'segment':1,
                    'offset':'','pending':None,'responses':0,'received':0,'saved_new':0}}
            self.save(j)
            self.repo.record_text_collection(bvid,kind,{'parts':selected,'total_parts':len(parts),'scope':scope,
                'authenticated':True,'complete':False,'interrupted':True,'job':j['id']})
            self.launch(j); return self.public(j)

    def launch(self,j):
        self.active=j['id']; self.provider.keys=None
        self.task=asyncio.create_task(self.run(j))

    async def resume(self,identity):
        async with self.lock:
            self.idle(); self.check_cooldown(); j=self.load(identity)
            self.ensure_video(j['bvid'])
            if j['status']=='complete': raise ProviderError('接口遍历已经结束，可新建任务刷新')
            if j['state'].get('retry_at',0)>time.time(): raise ProviderError('平台限制冷却中，请稍后继续')
            if not self.auth.cookies: raise ProviderError('请先登录')
            await self.auth.validate()
            if j['state']['owner']!=self.auth.account: raise ProviderError('请使用创建该任务的 Bilibili 账户继续')
            j['status']='running'; j['message']='从断点继续'; self.save(j); self.launch(j); return self.public(j)

    async def cancel(self,identity=None):
        async with self.lock:
            if self.task and not self.task.done() and (identity is None or identity==self.active):
                self.task.cancel()
                await self.task
            elif identity and self.load(identity)['status']=='running':
                raise ProviderError('当前运行任务不匹配')

    async def cancel_video(self,bvid):
        if self.active and self.load(self.active)['bvid']==bvid:
            await self.cancel(self.active)

    def save_dm(self,items):
        with self.db.connect() as c:
            before=c.total_changes
            for r in items:
                c.execute('''INSERT INTO danmaku(bvid,cid,progress_sec,text,send_time,captured_at,raw_text,source_id)
                    SELECT ?,?,?,?,?,?,NULL,? WHERE NOT EXISTS (
                    SELECT 1 FROM danmaku WHERE bvid=? AND cid=? AND source_id=?)''',
                    (r.bvid,r.cid,r.progress_sec,r.text,r.send_time,iso_now(),r.source_id,r.bvid,r.cid,r.source_id))
            return c.total_changes-before

    async def dm_step(self,j):
        s=j['state']; parts=s['parts']
        if s['part_index']>=len(parts): return True
        p=parts[s['part_index']]; count=max(1,math.ceil(p['duration']/360))
        if count>10000: raise ProviderError('视频时长异常，无法计算分段范围')
        rows=await self.provider.segment(j['bvid'],p['cid'],s['segment'])
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
            self.repo.insert_comments([comment(r,bvid) for r in unique.values()]); s['received']+=len(unique)
            end=cursor['is_end']; next_offset=(cursor.get('pagination_reply') or {}).get('next_offset')
            if not end and (not isinstance(next_offset,str) or not next_offset or next_offset==s['offset']):
                raise ProviderError('评论游标未前进，已保存本页，任务未完成')
            if not end:
                digest=hashlib.sha256(next_offset.encode()).hexdigest()
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
                d=await self.provider.children(s['aid'],root['id'],pending['page'])
                page=d.get('page') or {}; rows=d.get('replies') or []
                if len(rows)>100: raise ProviderError('楼中楼单页过多，任务已暂停')
                if 'count' not in page or int(page.get('num',0))!=pending['page'] or int(page.get('size',0))<=0:
                    raise ProviderError('楼中楼分页信息异常，任务未完成')
                count=int(page['count']); size=int(page['size'])
                end=pending['page']*size>=count
                if not rows and count>0: raise ProviderError('楼中楼返回空页但仍有计数，任务未完成')
                # True parent is retained when supplied; root is the fallback.
                parsed=[comment(r,bvid,str(r.get('parent_str') or r.get('parent') or root['id'])) for r in rows]
                self.repo.insert_comments(parsed); s['received']+=len(parsed)
                if end:
                    self.root_done(j['id'],root['id'],mark=True); pending['index']+=1; pending['page']=1
                else: pending['page']+=1
                break
        if pending['index']>=len(pending['roots']):
            s['offset']=pending['next'] or ''; s['pending']=None
            return pending['end']
        return False

    async def run(self,j):
        try:
            for _ in range(self.budget):
                self.ensure_video(j['bvid'])
                complete=j['state'].get('traversed',False)
                if not complete:
                    complete=await (self.dm_step(j) if j['kind']=='danmaku' else self.comments_step(j))
                    j['state']['responses']+=1
                j['state']['traversed']=complete
                j['message']='正在逐段读取' if j['kind']=='danmaku' else '正在读取评论及楼中楼'
                self.save(j)
                if complete:
                    j['status']='complete'; j['message']='接口遍历结束；不保证包含删除、不可见或完整历史内容'
                    self.repo.record_text_collection(j['bvid'],j['kind'],{**{k:j['state'][k] for k in ('parts','total_parts','scope','received','responses')},
                        'authenticated':True,'complete':False,'traversal_complete':True,'interrupted':False,'job':j['id']})
                    break
                await asyncio.sleep(0)  # Give cancellation and normal monitoring a scheduling point.
            else:
                j['status']='paused'; j['message']=f'本轮已处理 {self.budget} 个批次，点击继续读取后续数据'
        except asyncio.CancelledError:
            j['status']='paused'; j['message']='已暂停，已保存的数据和断点保留'
        except RiskControlError:
            j['status']='paused'; j['message']='平台限制或登录失效，已停止请求；10 分钟后可手动继续'
            j['state']['retry_at']=time.time()+600
        except ProviderError as e:
            j['status']='paused'; j['message']=str(e)
        except Exception:
            # Do not persist arbitrary exception strings that may contain credentials.
            j['status']='paused'; j['message']='响应结构或本地保存异常，进度已保留，请检查后继续'
        finally:
            self.save(j)

    async def shutdown(self):
        await self.cancel()
