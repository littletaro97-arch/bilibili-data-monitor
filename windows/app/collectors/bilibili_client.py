from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.database import Repository
from app.models import ProviderError, RiskControlError, LoginRequiredError


RISK_STATUS_CODES = {403, 412}


class BilibiliClient:
    def __init__(
        self,
        timeout: int = 10,
        min_interval_seconds: int = 3,
        max_retries: int = 2,
        repository: Repository | None = None,
    ):
        self.timeout = timeout
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self.repository = repository
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            wait_seconds = self.min_interval_seconds - elapsed
            if self._last_request_at and wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            last_error: Exception | None = None
            for attempt in range(self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(
                            url,
                            params=params,
                            headers={
                                "User-Agent": self.user_agent,
                                "Referer": "https://www.bilibili.com/",
                            },
                        )
                    self._last_request_at = time.monotonic()
                    if response.status_code in RISK_STATUS_CODES:
                        raise RiskControlError(f"请求被平台限制，HTTP {response.status_code}")
                    response.raise_for_status()
                    payload = response.json()
                    self._detect_risk_payload(payload)
                    return payload
                except RiskControlError as exc:
                    self._log("WARNING", "触发风控或访问限制，停止重试", detail=str(exc))
                    raise
                except (httpx.TimeoutException, httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        break
                    await asyncio.sleep(2**attempt)

            message = f"网络请求失败：{last_error}"
            self._log("ERROR", message)
            raise ProviderError(message)

    async def authenticated_response(self, url, cookies, params=None, *, binary=False):
        """Share the statistics request limiter; never forward credentials off-platform."""
        from urllib.parse import urlsplit
        target = urlsplit(url)
        if target.scheme != "https" or target.hostname != "api.bilibili.com" or target.port not in {None,443} or target.username:
            raise ProviderError("登录态只能发送给固定的平台 HTTPS 接口")
        async with self._lock:
            wait = max(3, self.min_interval_seconds) - (time.monotonic() - self._last_request_at)
            if self._last_request_at and wait > 0:
                await asyncio.sleep(wait)
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as session:
                    async with session.stream("GET",url,params=params,cookies=cookies,
                        headers={"User-Agent":self.user_agent,"Referer":"https://www.bilibili.com/"}) as response:
                        if response.status_code == 401:
                            raise LoginRequiredError("登录已失效，请重新扫码登录")
                        if response.status_code in {403,412,429}:
                            raise RiskControlError(f"平台拒绝请求，HTTP {response.status_code}；已停止，稍后再继续")
                        if response.status_code == 304:
                            raise ProviderError("平台返回未修改响应，不能作为分段已采集的依据")
                        response.raise_for_status()
                        content=bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content)>8*1024*1024:
                                raise ProviderError("平台单次响应超过 8 MiB，任务已暂停")
                        if binary and "json" not in response.headers.get("content-type", "").lower() and not content.startswith(b'{'):
                            return bytes(content)
                        payload = __import__('json').loads(content)
                        if not isinstance(payload,dict):
                            raise ProviderError('平台响应结构异常，进度已保留')
                        if payload.get('code') == -101:
                            raise LoginRequiredError('登录已失效，请重新扫码登录')
                        if payload.get('code') in {403,412,-403,-412,-352,-111}:
                            raise RiskControlError('平台限制或登录失效，任务已停止')
                        if payload.get("code") != 0:
                            raise ProviderError(f"平台接口失败：code={payload.get('code')}；任务未完成")
                        if binary:
                            raise ProviderError("弹幕分段接口返回 JSON 而不是 protobuf，任务未完成")
                        return payload
            except (httpx.HTTPError, ValueError):
                raise ProviderError("平台请求或响应解析失败，进度已保留") from None
            finally:
                self._last_request_at = time.monotonic()

    async def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            wait_seconds = self.min_interval_seconds - elapsed
            if self._last_request_at and wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            last_error: Exception | None = None
            for attempt in range(self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(
                            url,
                            params=params,
                            headers={
                                "User-Agent": self.user_agent,
                                "Referer": "https://www.bilibili.com/",
                            },
                        )
                    self._last_request_at = time.monotonic()
                    if response.status_code in RISK_STATUS_CODES:
                        raise RiskControlError(f"请求被平台限制，HTTP {response.status_code}")
                    response.raise_for_status()
                    return response.text
                except RiskControlError as exc:
                    self._log("WARNING", "触发风控或访问限制，停止重试", detail=str(exc))
                    raise
                except (httpx.TimeoutException, httpx.HTTPError) as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        break
                    await asyncio.sleep(2**attempt)

            message = f"网络请求失败：{last_error}"
            self._log("ERROR", message)
            raise ProviderError(message)

    def _detect_risk_payload(self, payload: dict[str, Any]) -> None:
        code = payload.get("code")
        message = str(payload.get("message", ""))
        risk_words = ("验证码", "风控", "登录", "访问权限", "账号")
        if code in {403, 412, -403, -412, -352, -101} or any(word in message for word in risk_words):
            raise RiskControlError(f"接口返回风险状态：code={code}, message={message}")

    def _log(self, level: str, message: str, detail: str | None = None) -> None:
        if self.repository:
            self.repository.add_log(level, message, detail=detail)
