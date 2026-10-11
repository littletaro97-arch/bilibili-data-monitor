"""Optional two-profile authentication with explicit, checkpoint-preserving handoff."""
from contextvars import ContextVar
from app.database import iso_now,parse_iso,local_now
from app.models import ProviderError,LoginRequiredError,RequestFailure

class ProfileClient:
    def __init__(self,engine,key):self.engine=engine;self.key=key
    @property
    def user_agent(self):return self.engine.user_agent
    @property
    def ssl_context(self):return self.engine.ssl_context
    async def authenticated_response(self,url,cookies,params=None,*,binary=False):
        return await self.engine.authenticated_response(url,cookies,params,binary=binary,profile_key=self.key)

class RoutingClient:
    def __init__(self,pool):self.pool=pool
    async def authenticated_response(self,url,cookies,params=None,*,binary=False):
        profile=self.pool.current()
        return await profile.client.authenticated_response(url,dict(profile.cookies),params,binary=binary)

class AccountPool:
    is_account_pool=True
    def __init__(self,primary,backup):
        self.profiles={'primary':primary,'backup':backup};self._bound=ContextVar('bili_account_profile',default=None)
        self.client=RoutingClient(self)
        for key,auth in self.profiles.items():
            def validator(data,key=key):
                other=self.profiles['backup' if key=='primary' else 'primary']
                if other.cookies and str(data['mid'])==other.account:raise ProviderError('主账号和备用账号请使用不同账户')
            auth.account_validator=validator
    def available(self):return [k for k,a in self.profiles.items() if a.cookies and a.verification!='expired']
    def preferred(self,target):
        import hashlib
        keys=self.available() or ['primary']
        return keys[int(hashlib.sha256(str(target).encode()).hexdigest(),16)%len(keys)]
    def default_key(self):
        available=self.available()
        if available:return available[0]
        return next((k for k,a in self.profiles.items() if a.cookies),'primary')
    def current_key(self):return self._bound.get() or self.default_key()
    def current(self):return self.profiles[self.current_key()]
    def bind(self,key):return self._bound.set(key)
    def unbind(self,token):self._bound.reset(token)
    @property
    def cooldown_seconds(self):
        import time,math
        engine=self.current().client.engine
        return max(0,math.ceil(engine._cooldown_until-time.monotonic()))
    @property
    def cookies(self):return self.current().cookies
    @property
    def account(self):return self.current().account
    @property
    def verification(self):return self.current().verification
    @property
    def last_verified_at(self):return self.current().last_verified_at
    def status(self):
        result=dict(self.profiles[self.default_key()].status())
        result['profiles']={k:a.status() for k,a in self.profiles.items()}
        result['active_profile']=self.default_key();result['backup_optional']=True
        return result
    async def verify(self,key,force=False):
        a=self.profiles[key]
        if not a.cookies:raise LoginRequiredError('该账号未登录')
        verified=parse_iso(a.last_verified_at) if a.last_verified_at else None
        if not force and a.verification=='valid' and verified and (local_now()-verified).total_seconds()<300:return None
        return await a.validate()
    async def choose(self,owner=None,owner_profile=None,*,allow_rebind=False):
        match=next((k for k,a in self.profiles.items() if owner and a.account==owner),None)
        if owner and not match and owner_profile and self.profiles[owner_profile].cookies and not allow_rebind:
            raise RequestFailure('account','原账号已更换为另一账户，请确认任务归属后继续')
        preferred=match or owner_profile or self.default_key()
        candidates=[preferred]+[k for k in self.profiles if k!=preferred]
        for key in candidates:
            a=self.profiles[key]
            if not a.cookies or a.verification=='expired':continue
            try:await self.verify(key)
            except LoginRequiredError:
                a.verification='expired';a.verification_error='平台已确认登录失效';continue
            return key
        raise LoginRequiredError('没有可用登录账号，请登录主账号或备用账号')
    async def validate(self):
        bound=self._bound.get()
        key=bound or await self.choose()
        a=self.profiles[key];verified=parse_iso(a.last_verified_at) if a.last_verified_at else None
        if a.verification=='valid' and verified and (local_now()-verified).total_seconds()<300 and hasattr(a,'_validated_data'):return a._validated_data
        return await a.validate()
    async def expired(self,error):
        a=self.current()
        if not error.confirmed:
            # A content-specific HTTP401 is not enough to declare the whole account expired.
            try:await a.validate()
            except LoginRequiredError:pass
            else:raise RequestFailure('account','账号验证有效，但当前内容的访问被拒绝；保留断点，不自动换号')
        a.verification='expired';a.verification_error='平台已确认登录失效'
    async def close(self):
        for a in self.profiles.values():await a.close()
