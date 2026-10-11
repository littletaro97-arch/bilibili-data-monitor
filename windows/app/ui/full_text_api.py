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
    local(request); pool=request.app.state.bili_auth;service=request.app.state.full_text
    value=await body(request);profile=str(value.get('profile','primary'))
    is_pool=getattr(pool,'is_account_pool',False) is True
    if profile not in {'primary','backup'} or (not is_pool and profile!='primary'):raise HTTPException(400,'账号位置不正确')
    auth=pool.profiles[profile] if is_pool else pool
    def decorate(result):
        return result | {'profiles':pool.status()['profiles']} if is_pool and 'saved' in result else result
    try:
        if action=='verify':
            try:await auth.validate()
            except ProviderError:pass
            return decorate(auth.status())
        if action=='logout':
            if is_pool:await service.account_exit(profile)
            else:await service.cancel()
        async with service.lock:
            if not is_pool:service.idle()
            elif service.task and not service.task.done() and service._running_job['state'].get('owner_profile','primary')==profile:
                raise ProviderError('该账号正在采集，请等待当前批次完成或先暂停')
            if action=='qr':return await auth.qrcode()
            if action in {'poll','save'}:
                result=await auth.poll() if action=='poll' else await auth.save_sessdata(str(value.get('sessdata','')))
                if is_pool and (result.get('status')=='ok' or action=='save') and hasattr(request.app.state,'up_monitor'):
                    request.app.state.up_monitor.store.resume_login_tasks()
                return decorate(result)
            if action=='logout':
                await auth.logout()
                if is_pool:await auth.client.engine.close_profile('account:'+profile)
                if hasattr(request.app.state,'up_monitor') and (not is_pool or not pool.available()):request.app.state.up_monitor.store.require_login()
                return decorate(auth.status())
            raise HTTPException(404)
    except ProviderError as e:return JSONResponse({'error':str(e)},status_code=400)



@router.get('/jobs/{bvid}')
async def latest(bvid:str,request:Request):
    local(request); return {'job':request.app.state.full_text.latest(bvid),'jobs':request.app.state.full_text.jobs(bvid)}


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
