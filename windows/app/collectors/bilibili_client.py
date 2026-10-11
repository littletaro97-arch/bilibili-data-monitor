from __future__ import annotations

import asyncio
import time
import os
import ssl
import certifi
from typing import Any

import httpx

from app.database import Repository
from app.models import ProviderError, RiskControlError, LoginRequiredError, RequestFailure, CommentUnavailableError, CommentCursorError


RISK_STATUS_CODES = {403, 412, 429}


class BilibiliClient:
    def __init__(
        self,
        timeout: int = 10,
        min_interval_seconds: float = .75,
        max_retries: int = 2,
        repository: Repository | None = None,
        risk_cooldown_seconds: float = 600,
    ):
        self.timeout = timeout
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self.repository = repository
        self.risk_cooldown_seconds = risk_cooldown_seconds
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._sessions = {}
        self._ssl_context = None
        self._closed = False
        self._cooldown_until = 0.0
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )

    @property
    def ssl_context(self):
        if self._ssl_context is None:
            ca_file=os.environ.get('SSL_CERT_FILE')
            ca_dir=os.environ.get('SSL_CERT_DIR')
            self._ssl_context=ssl.create_default_context(cafile=ca_file or (None if ca_dir else certifi.where()),capath=ca_dir if not ca_file else None)
        return self._ssl_context

    def _session(self,key):
        if self._closed:raise ProviderError('请求通道已关闭')
        if key not in self._sessions:
            self._sessions[key]=httpx.AsyncClient(timeout=self.timeout,verify=self.ssl_context,
                limits=httpx.Limits(max_connections=1,max_keepalive_connections=1,keepalive_expiry=30))
        return self._sessions[key]

    async def _wait_start(self):
        if time.monotonic()<self._cooldown_until:raise RiskControlError('平台限制，共享请求通道仍在冷却')
        wait=self.min_interval_seconds-(time.monotonic()-self._last_request_at)
        if self._last_request_at and wait>0:await asyncio.sleep(wait)
        if time.monotonic()<self._cooldown_until:raise RiskControlError('平台限制，共享请求通道仍在冷却')
        self._last_request_at=time.monotonic()

    def defer_risk(self,seconds=None):
        self._cooldown_until=max(self._cooldown_until,time.monotonic()+(self.risk_cooldown_seconds if seconds is None else seconds))

    async def close(self):
        async with self._lock:
            self._closed=True
            sessions=list(self._sessions.values());self._sessions.clear()
            for session in sessions:await session.aclose()

    async def close_profile(self,key):
        async with self._lock:
            session=self._sessions.pop(key,None)
            if session is not None:await session.aclose()

    async def _public(self,url,params,text=False):
        async with self._lock:
            last_error=None
            for attempt in range(self.max_retries+1):
                await self._wait_start()
                try:
                    client=self._session('public');client.cookies.clear()
                    response=await client.get(url,params=params,headers={'User-Agent':self.user_agent,'Referer':'https://www.bilibili.com/'})
                    if response.status_code in RISK_STATUS_CODES:raise RiskControlError(f'请求被平台限制，HTTP {response.status_code}')
                    response.raise_for_status()
                    if text:return response.text
                    payload=response.json();self._detect_risk_payload(payload);return payload
                except RiskControlError:
                    self.defer_risk();raise
                except (httpx.HTTPError,ValueError) as exc:
                    last_error=exc
                    if isinstance(exc,httpx.TransportError) or attempt>=self.max_retries:break
                    await asyncio.sleep(2**attempt)
            raise request_failure(last_error) from None

    async def get_json(self,url,params=None):return await self._public(url,params)
    async def get_text(self,url,params=None):return await self._public(url,params,text=True)

    async def authenticated_response(self,url,cookies,params=None,*,binary=False,profile_key='primary'):
        from urllib.parse import urlsplit
        target=urlsplit(url)
        if target.scheme!='https' or target.hostname!='api.bilibili.com' or target.port not in {None,443} or target.username:
            raise ProviderError('登录态只能发送给固定的平台 HTTPS 接口')
        async with self._lock:
            await self._wait_start()
            try:
                session=self._session('account:'+profile_key)
                # Each account has its own pool. Explicit credentials also replace stale response cookies.
                session.cookies.clear()
                async with session.stream('GET',url,params=params,cookies=dict(cookies),
                    headers={'User-Agent':self.user_agent,'Referer':'https://www.bilibili.com/'}) as response:
                    if response.status_code==401:raise LoginRequiredError('登录请求被拒绝，需要核验登录态',confirmed=False)
                    if response.status_code in {403,412,429}:raise RiskControlError(f'平台拒绝请求，HTTP {response.status_code}')
                    if response.status_code==304:raise ProviderError('平台返回未修改响应，不能作为分段已采集的依据')
                    response.raise_for_status();content=bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content)>8*1024*1024:raise ProviderError('平台单次响应超过 8 MiB，任务已暂停')
                    if binary and 'json' not in response.headers.get('content-type','').lower() and not content.startswith(b'{'):
                        return bytes(content)
                    payload=__import__('json').loads(content)
                    if not isinstance(payload,dict):raise ProviderError('平台响应结构异常，进度已保留')
                    if payload.get('code')==-101:raise LoginRequiredError('登录已失效，请重新扫码登录')
                    if payload.get('code') in {403,412,-403,-412,-352,-111}:raise RiskControlError('平台限制请求，断点保留')
                    if payload.get('code')==12006 and target.path=='/x/v2/reply/reply':raise CommentUnavailableError('楼中楼对应的根评论已不可见')
                    if payload.get('code')==-400 and target.path=='/x/v2/reply/wbi/main':raise CommentCursorError('评论分页参数被拒绝，断点保留')
                    if payload.get('code')!=0:raise ProviderError(f"平台接口失败：code={payload.get('code')}；任务未完成")
                    if binary:raise ProviderError('弹幕分段接口返回 JSON 而不是 protobuf，任务未完成')
                    return payload
            except LoginRequiredError:raise
            except RiskControlError:
                self.defer_risk();raise
            except (httpx.HTTPError,ValueError) as exc:raise request_failure(exc) from None

    def _detect_risk_payload(self, payload: dict[str, Any]) -> None:
        code = payload.get("code")
        message = str(payload.get("message", ""))
        risk_words = ("验证码", "风控", "登录", "访问权限", "账号")
        if code in {403, 412, -403, -412, -352, -101} or any(word in message for word in risk_words):
            raise RiskControlError(f"接口返回风险状态：code={code}, message={message}")

    def _log(self, level: str, message: str, detail: str | None = None) -> None:
        if self.repository:
            self.repository.add_log(level, message, detail=detail)


def request_failure(exc):
    # Never include exception text, request headers, cookies or response bodies.
    if isinstance(exc,httpx.TimeoutException):return RequestFailure('timeout','网络请求超时，登录态与采集进度已保留')
    if isinstance(exc,httpx.HTTPStatusError):return RequestFailure('http',f'平台 HTTP {exc.response.status_code}，采集进度已保留')
    if isinstance(exc,httpx.HTTPError):return RequestFailure('network','网络连接失败，登录态与采集进度已保留')
    return RequestFailure('parse','平台响应无法解析为有效 JSON，采集进度已保留')
