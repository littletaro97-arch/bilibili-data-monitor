"""Identify one explicit UP/video target without guessing authors from video links."""
import re
from urllib.parse import urlsplit
import httpx
from app.collectors.video_info import parse_bvid
from app.models import InvalidBvidError


def classify_target(text):
    text=(text or '').strip()
    if not text or len(text)>2048:raise InvalidBvidError('请填写一个 UP UID、空间链接、BV 号或视频链接')
    numeric=re.fullmatch(r'(?:UID\s*[:：]?\s*)?(\d+)',text,re.I)
    if numeric:
        value=int(numeric[1])
        if not 0<value<2**63:raise InvalidBvidError('UP UID 不正确')
        return 'up',str(value)
    urls=re.findall(r'https?://[^\s<>"，]+|(?<![\w@./])(?:space\.bilibili\.com|www\.bilibili\.com|m\.bilibili\.com|bilibili\.com|b23\.tv)/[^\s<>"，]+',text,re.I)
    if len(urls)>1:raise InvalidBvidError('一次只添加一个 UP 或视频链接')
    if urls:
        url=urls[0].rstrip('。；;)）')
        if not url.lower().startswith(('http://','https://')):url='https://'+url
        try:
            parsed=urlsplit(url);port=parsed.port
        except ValueError:raise InvalidBvidError('链接格式不正确') from None
        if parsed.username or parsed.password or port not in {None,443} or parsed.scheme!='https':
            raise InvalidBvidError('请使用无账号密码的官方 HTTPS 链接')
        if parsed.hostname=='space.bilibili.com':
            mid=parsed.path.strip('/').split('/')[0]
            if not mid.isdigit() or not 0<int(mid)<2**63:raise InvalidBvidError('UP 空间链接中的 UID 不正确')
            return 'up',str(int(mid))
        if parsed.hostname=='b23.tv':return 'short',url
        if parsed.hostname not in {'www.bilibili.com','bilibili.com','m.bilibili.com'} or not parsed.path.lower().startswith('/video/'):
            raise InvalidBvidError('请填写官方 UP 空间或视频链接')
        return 'video',parse_bvid(url)
    ids=re.findall(r'(?<![0-9A-Za-z])BV[0-9A-Za-z]{10}(?![0-9A-Za-z])',text)
    if len(set(ids))!=1:raise InvalidBvidError('请填写一个 UP UID、空间链接、BV 号或视频链接')
    return 'video',ids[0]


async def resolve_target(text,*,transport=None):
    kind,value=classify_target(text)
    if kind!='short':return kind,value
    try:
        async with httpx.AsyncClient(timeout=15,transport=transport,follow_redirects=False) as client:
            for _ in range(5):
                kind,target=classify_target(value)
                if kind!='short':return kind,target
                response=await client.get(target)
                if not response.is_redirect or response.next_request is None:raise InvalidBvidError('短链未返回有效 UP 或视频地址')
                value=str(response.next_request.url)
    except (httpx.HTTPError,ValueError):raise InvalidBvidError('短链解析失败，请检查网络或填写完整链接') from None
    raise InvalidBvidError('短链跳转次数过多')
