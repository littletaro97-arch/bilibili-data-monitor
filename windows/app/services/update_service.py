from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

import httpx

from app.version import PACKAGE_VERSION

REPOSITORY = "littletaro97-arch/bilibili-data-monitor"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
ASSET_PATTERN = re.compile(r"BilibiliMonitor-v(\d+\.\d+\.\d+)-installer\.(\d+)-windows-x64-setup\.exe")
MAX_PACKAGE_BYTES = 512 * 1024 * 1024


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class UpdatePackage:
    version: tuple[int, ...]
    name: str
    url: str
    digest: str | None
    size: int
    release_url: str
    notes: str

    @property
    def display_version(self):
        return f"{'.'.join(map(str, self.version[:3]))} · 安装包第 {self.version[3]} 版"


def package_from_release(release: dict, asset: dict) -> UpdatePackage | None:
    match = ASSET_PATTERN.fullmatch(str(asset.get("name", "")))
    if not match or asset.get("state") != "uploaded":
        return None
    name = match.group(0)
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not tag:
        return None
    expected = f"https://github.com/{REPOSITORY}/releases/download/{quote(tag, safe='')}/{name}"
    url = asset.get("browser_download_url")
    if url != expected:
        return None
    size = asset.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_PACKAGE_BYTES:
        return None
    digest = asset.get("digest")
    digest = digest[7:].lower() if isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest) else None
    return UpdatePackage(
        tuple(map(int, match[1].split("."))) + (int(match[2]),), name, url, digest, size,
        f"{RELEASES_URL}/tag/{quote(tag, safe='')}", str(release.get("body") or "暂无更新说明。")[:12000],
    )


def safe_download_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and not parsed.username and not parsed.password
                and parsed.port in {None, 443} and parsed.hostname in {
                    "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
                })
    except ValueError:
        return False


class UpdateService:
    def __init__(self, download_dir: Path, transport=None):
        self.download_dir = download_dir
        self.transport = transport
        self.package: UpdatePackage | None = None
        self.status = "尚未检查更新。"
        self.checked = False
        self._check_lock = asyncio.Lock()
        self._download_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return self.package is not None and self.package.version > tuple(map(int, PACKAGE_VERSION.split(".")))

    def client(self):
        return httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10), transport=self.transport,
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "BilibiliMonitor-Windows"})

    async def check(self) -> None:
        async with self._check_lock:
            self.package = None
            self.checked = True
            try:
                candidates = []
                async with self.client() as client:
                    for page in range(1, 11):
                        response = await client.get(f"https://api.github.com/repos/{REPOSITORY}/releases", params={"per_page": 100, "page": page})
                        if response.status_code in {403, 429}:
                            raise UpdateError("GitHub 暂时限制请求，请稍后重试或打开发布页。")
                        if response.status_code == 404:
                            raise UpdateError("无法访问公开更新仓库，请查看发布页或稍后重试。")
                        response.raise_for_status()
                        releases = response.json()
                        if not isinstance(releases, list):
                            raise UpdateError("GitHub 返回的版本信息格式异常。")
                        for release in releases:
                            if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
                                continue
                            assets = release.get("assets", [])
                            if not isinstance(assets, list):
                                raise UpdateError("GitHub 返回的安装包信息格式异常。")
                            for asset in assets:
                                if isinstance(asset, dict):
                                    package = package_from_release(release, asset)
                                    if package:
                                        candidates.append(package)
                        if len(releases) < 100:
                            break
                    else:
                        raise UpdateError("发布记录过多，检查未完成，请打开发布页。")
                self.package = max(candidates, key=lambda package: package.version, default=None)
                if not self.package:
                    self.status = "尚无正式发布的 Windows x64 安装包。"
                elif self.available:
                    self.status = "发现电脑版更新。" if self.package.digest else "发现电脑版更新，但缺少 SHA-256 校验信息，暂不可在此下载。"
                else:
                    self.status = "当前版本不低于已发布的电脑版安装包。"
            except UpdateError as exc:
                self.status = str(exc)
            except (httpx.HTTPError, ValueError, TypeError):
                self.status = "检查更新失败，请检查网络或稍后重试。"

    async def download(self) -> tuple[Path, str]:
        async with self._download_lock:
            package = self.package
            if not self.available or package is None or not package.digest:
                raise UpdateError("请先检查更新，并选择具有 SHA-256 校验信息的新版本。")
            self.download_dir.mkdir(parents=True, exist_ok=True)
            # Content-addressed filenames prevent a repeated publish from reusing an old file.
            target = self.download_dir / f"{package.digest}-{package.name}"
            partial = target.with_suffix(".part")
            try:
                digest = hashlib.sha256()
                received = 0
                async with self.client() as client:
                    url = package.url
                    for _ in range(6):
                        if not safe_download_url(url):
                            raise UpdateError("更新包重定向到未受信任地址，下载已停止。")
                        async with client.stream("GET", url) as response:
                            if response.is_redirect:
                                url = str(response.next_request.url) if response.next_request else ""
                                continue
                            response.raise_for_status()
                            with partial.open("wb") as stream:
                                async for chunk in response.aiter_bytes():
                                    received += len(chunk)
                                    if received > package.size or received > MAX_PACKAGE_BYTES:
                                        raise UpdateError("更新包大小异常，下载已停止。")
                                    digest.update(chunk)
                                    stream.write(chunk)
                            break
                    else:
                        raise UpdateError("更新包重定向过多，下载已停止。")
                if received != package.size or digest.hexdigest() != package.digest:
                    raise UpdateError("更新包 SHA-256 或大小校验失败，请重新检查更新后重试。")
                partial.replace(target)
                return target, package.name
            except httpx.HTTPError as exc:
                raise UpdateError("更新包下载失败，请检查网络或稍后重试。") from exc
            except OSError as exc:
                raise UpdateError("无法保存更新包，请检查磁盘空间或目录权限。") from exc
            finally:
                partial.unlink(missing_ok=True)
