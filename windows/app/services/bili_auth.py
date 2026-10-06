"""Local-only login UI; credentials are DPAPI protected and never returned to HTML."""
import asyncio
import base64
import ctypes
from ctypes import wintypes
from io import BytesIO
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import httpx

from app.models import ProviderError, LoginRequiredError

NAV = "https://api.bilibili.com/x/web-interface/nav"
PASSPORT = "https://passport.bilibili.com/x/passport-login/web/qrcode/"


def protect(data: bytes, *, decrypt=False) -> bytes:
    if os.name != 'nt':
        raise ProviderError("持久登录态需要 Windows 用户加密保护")
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=(ctypes.c_ubyte*len(data)).from_buffer_copy(data)
    source=Blob(len(data),buffer);out=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(out)):
        raise ProviderError("Windows 无法保护或读取登录态，请在当前账户重新登录")
    kernel=ctypes.WinDLL('kernel32');kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:kernel.LocalFree(out.pbData)


class BiliAuth:
    def __init__(self,path:Path,client):
        self.path=path;self.client=client;self.cookies={};self.name='';self.account='';self.error='';self.pending=None
        self._passport=None;self._lock=asyncio.Lock()
        if path.exists():
            try:
                if path.stat().st_size>65536: raise ValueError('invalid saved state')
                saved=json.loads(protect(path.read_bytes(),decrypt=True));self.cookies=saved['cookies'];self.name=saved['name'];self.account=saved['account']
            except Exception:
                self.error='保存的登录态不可读取，请重新登录'

    def status(self):
        return {'saved':bool(self.cookies.get('SESSDATA')),'name':self.name,'message':self.error or ('已保存登录态，开始采集时会验证有效性' if self.cookies else '尚未登录')}

    async def validate(self,cookies=None):
        payload=await self.client.authenticated_response(NAV,self.cookies if cookies is None else cookies)
        data=payload.get('data') or {}
        if not data.get('isLogin') or not data.get('mid'):
            raise LoginRequiredError('登录已失效，请重新扫码登录')
        return data

    async def save(self,cookies):
        cookies={k:str(v) for k,v in cookies.items() if k in {'SESSDATA','bili_jct','DedeUserID','DedeUserID__ckMd5','buvid3','buvid4'} and v}
        data=await self.validate(cookies)
        saved={'cookies':cookies,'name':str(data.get('uname') or ''),'account':str(data['mid'])}
        encoded=protect(json.dumps(saved,ensure_ascii=False).encode('utf-8'))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.pending');temp.write_bytes(encoded);temp.replace(self.path)
        self.cookies=cookies;self.name=saved['name'];self.account=saved['account'];self.error=''
        return self.status()

    async def save_sessdata(self,value):
        match=re.search(r'(?:^|[;\s])SESSDATA=([^;\s]+)',value)
        value=match.group(1) if match else value.strip()
        if not value or len(value)>4096 or any(c in value for c in '\r\n;'):
            raise ProviderError('SESSDATA 格式不正确')
        return await self.save({'SESSDATA':value})

    async def _session(self):
        if self._passport is None:
            self._passport=httpx.AsyncClient(timeout=15,headers={'User-Agent':self.client.user_agent,'Referer':'https://www.bilibili.com/'})
        return self._passport

    async def qrcode(self):
        import qrcode
        async with self._lock:
            if self.pending and time.monotonic()-self.pending['created']<3:
                raise ProviderError('二维码申请过于频繁，请稍后再试')
            session=await self._session()
            session.cookies.clear()
            try:
                r=await session.get(PASSPORT+'generate');r.raise_for_status();payload=r.json();data=payload.get('data') or {}
                if payload.get('code')!=0:raise ProviderError('二维码申请失败')
                url=data['url'];parts=urlsplit(url)
                if parts.scheme!='https' or not (parts.hostname or '').endswith('.bilibili.com'):raise ProviderError('二维码登录地址异常')
                self.pending={'key':data['qrcode_key'],'created':time.monotonic(),'last_poll':0}
                image=BytesIO();qrcode.make(url).save(image,format='PNG')
                return {'image':'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode('ascii')}
            except (httpx.HTTPError,ValueError,KeyError):raise ProviderError('二维码申请失败，请稍后重试') from None

    async def poll(self):
        async with self._lock:
            pending=self.pending
            if not pending or time.monotonic()-pending['created']>180:
                self.pending=None
                return {'status':'expired'}
            if time.monotonic()-pending['last_poll']<2:return {'status':'waiting'}
            pending['last_poll']=time.monotonic()
            try:
                session=await self._session();r=await session.get(PASSPORT+'poll',params={'qrcode_key':pending['key']});r.raise_for_status();payload=r.json()
                if payload.get('code')!=0:raise ProviderError('扫码状态读取失败')
                code=(payload.get('data') or {}).get('code')
                if code==0:
                    cookies={c.name:c.value for c in session.cookies.jar if (c.domain or '').lstrip('.') in {'bilibili.com','passport.bilibili.com'}}
                    if not cookies.get('SESSDATA'):raise ProviderError('扫码成功但未获得登录态，请重新申请二维码')
                    await self.save(cookies);self.pending=None
                    return {'status':'ok',**self.status()}
                return {'status':{86038:'expired',86090:'scanned',86101:'waiting'}.get(code,'error')}
            except (httpx.HTTPError,ValueError):raise ProviderError('扫码状态读取失败，请重试') from None

    async def logout(self):
        self.cookies={};self.name='';self.account='';self.error='';self.pending=None
        self.path.unlink(missing_ok=True)
        await self.close()

    async def close(self):
        if self._passport:
            await self._passport.aclose();self._passport=None
