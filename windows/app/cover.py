from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


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
