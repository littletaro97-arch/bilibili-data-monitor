"""Fixed UP space endpoint using the existing, account-protected request channel."""
import re
import time
from urllib.parse import urlsplit
from app.collectors.full_text import sign
from app.models import LoginRequiredError, ProviderError

class UpVideoProvider:
    def __init__(self, client, auth):
        self.client=client; self.auth=auth; self.keys=None; self.keys_at=0; self.keys_cache={}

    async def page(self,mid,page=1):
        if not (getattr(self.auth,'is_account_pool',False) is True):return await self._page(mid,page)
        for _ in range(2):
            key=await self.auth.choose(owner_profile=self.auth.preferred(mid));token=self.auth.bind(key)
            try:
                if getattr(self,'keys_owner',None)!=self.auth.account:
                    cached=self.keys_cache.get(self.auth.account)
                    self.keys,self.keys_at=cached if cached else (None,0);self.keys_owner=self.auth.account
                return await self._page(mid,page)
            except LoginRequiredError as exc:
                await self.auth.expired(exc);self.keys=None
            finally:self.auth.unbind(token)
        raise LoginRequiredError('两个账号均不可用，UP分页断点保留')

    async def _page(self, mid, page=1):
        if not self.auth.status()['saved']:
            raise LoginRequiredError('请先在设置中扫码登录 Bilibili')
        if not self.keys or time.monotonic()-self.keys_at>86400:
            data=await self.auth.validate()
            images=data.get('wbi_img') or {}
            try:self.keys=tuple(urlsplit(images[k]).path.rsplit('/',1)[-1].split('.')[0] for k in ('img_url','sub_url'))
            except (KeyError,TypeError):raise ProviderError('平台未返回签名参数') from None
            self.keys_at=time.monotonic()
            self.keys_cache[getattr(self.auth,"account",None)]=(self.keys,self.keys_at)
        params=sign({'mid':mid,'pn':page,'ps':30,'order':'pubdate'},*self.keys)
        payload=await self.client.authenticated_response('https://api.bilibili.com/x/space/wbi/arc/search',dict(self.auth.cookies),params)
        data=payload.get('data')
        if not isinstance(data,dict) or not isinstance(data.get('list'),dict) or not isinstance(data.get('page'),dict):raise ProviderError('UP 投稿列表结构异常，基线未推进')
        listing=data['list'].get('vlist')
        if not isinstance(listing,list) or len(listing)>30:raise ProviderError('UP 投稿列表结构异常，基线未推进')
        rows=[]
        for row in listing:
            if not isinstance(row,dict):raise ProviderError('UP 投稿字段异常，基线未推进')
            try:
                bvid=str(row['bvid']); stamp=int(row['created'])
                if not re.fullmatch(r'BV[0-9A-Za-z]{10}',bvid) or not 0<stamp<2**63:raise ValueError()
                owner=int(row['mid'])
                if not 0<owner<2**63:raise ValueError()
                # Collaboration records listed in this space also belong to this monitor.
                rows.append({'bvid':bvid,'pubdate':stamp,'title':str(row.get('title') or bvid),
                             'author':str(row.get('author') or ''),'owner_mid':owner})
            except (KeyError,TypeError,ValueError):raise ProviderError('UP 投稿字段异常，基线未推进') from None
        try:total=int((data.get('page') or {})['count'])
        except (KeyError,TypeError,ValueError):raise ProviderError('UP 投稿分页信息异常，基线未推进') from None
        if total<0 or ((page-1)*30<total and not listing):raise ProviderError('UP 投稿列表为空但计数非空，基线未推进')
        return rows,total
