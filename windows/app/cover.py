from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit
from urllib.parse import urljoin
import asyncio
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import os
import tempfile

import httpx
from PIL import Image


def cover_key(url: str) -> str:
    return sha256(url.encode("utf-8")).hexdigest()


def local_cover_url(bvid: str, value: str | None) -> str | None:
    url = safe_cover_url(value)
    return f"/covers/{bvid}/{cover_key(url)}.webp" if url else None


class CoverCache:
    """Bounded disk cache. Metadata retains the original URL for data exchange."""

    MAX_DOWNLOAD = 5 * 1024 * 1024
    MAX_PIXELS = 20_000_000
    MAX_BYTES = 128 * 1024 * 1024
    MAX_FILES = 512

    def __init__(self, directory: Path, transport=None):
        self.directory = directory
        self.transport = transport
        # One download at a time also deduplicates concurrent requests for a cover.
        self._lock = asyncio.Lock()

    async def get(self, url: str) -> Path:
        if safe_cover_url(url) != url:
            raise ValueError("Untrusted cover URL")
        path = self.directory / (cover_key(url) + ".webp")
        if path.is_file():
            return path
        async with self._lock:
            if not path.is_file():
                await asyncio.to_thread(self._download, url, path)
        return path

    def _download(self, url: str, path: Path) -> None:
        with httpx.Client(timeout=httpx.Timeout(10, connect=5), transport=self.transport, follow_redirects=False) as client:
            for _ in range(4):
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        target = safe_cover_url(urljoin(url, response.headers.get("location", "")))
                        if not target:
                            raise ValueError("Untrusted cover redirect")
                        url = target
                        continue
                    response.raise_for_status()
                    if not response.headers.get("content-type", "").lower().startswith("image/"):
                        raise ValueError("Cover response is not an image")
                    if int(response.headers.get("content-length", "0")) > self.MAX_DOWNLOAD:
                        raise ValueError("Cover too large")
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > self.MAX_DOWNLOAD:
                            raise ValueError("Cover too large")
                    break
            else:
                raise ValueError("Too many cover redirects")
        # Decode only on cache miss; keep decoded image size appropriate for the UI.
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > self.MAX_PIXELS:
                raise ValueError("Cover dimensions too large")
            image.thumbnail((960, 960))
            converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            self.directory.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            try:
                with os.fdopen(handle, "wb") as stream:
                    converted.save(stream, format="WEBP", quality=85)
                self._prune(Path(temporary).stat().st_size)
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)

    def _prune(self, incoming: int) -> None:
        files = sorted(self.directory.glob("*.webp"), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        while files and (total + incoming > self.MAX_BYTES or len(files) >= self.MAX_FILES):
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink(missing_ok=True)


def safe_cover_url(value: str | None) -> str | None:
    """Use HTTPS for public Bilibili CDN images; never render arbitrary imported URLs."""
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        trusted = any(host == domain or host.endswith("." + domain) for domain in ("hdslb.com", "bilibili.com"))
        if not trusted or parsed.scheme not in {"http", "https"}:
            return None
        if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
            return None
        return urlunsplit(("https", host, parsed.path, parsed.query, ""))
    except ValueError:
        return None
