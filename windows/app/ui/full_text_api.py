"""Account management and manual authenticated collection are loopback-only."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from app.models import ProviderError

router=APIRouter(prefix='/api/text')


def local(request):
    if not request.client or request.client.host not in {'127.0.0.1','::1','localhost'} or request.url.hostname not in {'127.0.0.1','::1','localhost'}:
        raise HTTPException(403,'登录和登录采集仅允许本机操作')
    origin=request.headers.get('origin')
    if (origin and origin!=str(request.base_url).rstrip('/')) or request.headers.get('sec-fetch-site')=='cross-site':
        raise HTTPException(403,'不允许跨站操作')


async def body(request):
    try: length=int(request.headers.get('content-length','0'))
    except ValueError: raise HTTPException(400,'请求长度格式错误') from None
    if length>8192: raise HTTPException(413,'请求过大')
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>8192: raise HTTPException(413,'请求过大')
    import json
    try:
        value=json.loads(content or b'{}')
        if not isinstance(value,dict): raise ValueError()
        return value
    except ValueError: raise HTTPException(400,'参数格式错误') from None


@router.get('/auth')
async def status(request:Request):
    local(request); return request.app.state.bili_auth.status()


@router.post('/auth/{action}')
async def account(action:str,request:Request):
    local(request); auth=request.app.state.bili_auth; service=request.app.state.full_text
    try:
        if action=='verify':
            try: await auth.validate()
            except ProviderError: pass
            return auth.status()
        if action=='logout':
            await service.cancel()
        async with service.lock:
            service.idle()
            if action=='qr': return await auth.qrcode()
            if action=='poll': return await auth.poll()
            if action=='save': return await auth.save_sessdata(str((await body(request)).get('sessdata','')))
            if action=='logout':
                await auth.logout()
                if hasattr(request.app.state,"up_monitor"):
                    request.app.state.up_monitor.store.require_login()
                return auth.status()
            raise HTTPException(404)
    except ProviderError as e: return JSONResponse({'error':str(e)},status_code=400)


@router.get('/jobs/{bvid}')
async def latest(bvid:str,request:Request):
    local(request); return {'job':request.app.state.full_text.latest(bvid)}


@router.post('/jobs/{bvid}/{action}')
async def job(bvid:str,action:str,request:Request):
    local(request); service=request.app.state.full_text; value=await body(request)
    try:
        if action=='start':
            try: cid=int(value.get('cid') or 0)
            except (TypeError,ValueError): raise ProviderError('分 P 参数不正确') from None
            result=await service.start(bvid,value.get('kind'),value.get('scope','selected'),cid,continuous=value.get('continuous') is True)
        elif action in {'resume','cancel'}:
            identity=str(value.get('id') or '')
            if service.load(identity)['bvid']!=bvid: raise ProviderError('任务视频不匹配')
            if action=='resume': result=await service.resume(identity,continuous=value.get('continuous') is True)
            else: await service.cancel(identity); result=service.public(service.load(identity))
        else: raise HTTPException(404)
        return {'job':result}
    except ProviderError as e: return JSONResponse({'error':str(e)},status_code=400)
