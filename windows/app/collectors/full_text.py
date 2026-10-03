"""Authenticated, bounded requests. Traversal is not proof of historical completeness."""
import hashlib
import json
import time
from functools import lru_cache
from urllib.parse import urlencode, urlsplit

from app.models import DanmakuItem, VideoComment, ProviderError

MIXIN = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
API = 'https://api.bilibili.com'


def sign(params, img, sub, timestamp=None):
    key = img + sub
    if len(key) != 64:
        raise ProviderError('WBI 签名密钥格式异常')
    mixin = ''.join(key[i] for i in MIXIN)[:32]
    values = {k: ''.join(c for c in str(v) if c not in "!'()*") for k,v in params.items()}
    values['wts'] = str(int(time.time() if timestamp is None else timestamp))
    values = dict(sorted(values.items()))
    values['w_rid'] = hashlib.md5((urlencode(values) + mixin).encode()).hexdigest()
    return values


@lru_cache(maxsize=1)
def segment_message():
    # Lazy dynamic descriptor keeps protobuf out of the normal monitoring startup.
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
    f = descriptor_pb2.FileDescriptorProto(name='monitor_dm.proto', package='monitor', syntax='proto3')
    elem = f.message_type.add(name='Elem')
    for name,number,kind in [('id',1,3),('progress',2,5),('mode',3,5),('fontsize',4,5),('color',5,13),('midHash',6,9),('content',7,9),('ctime',8,3),('weight',9,5),('idStr',12,9)]:
        elem.field.add(name=name,number=number,type=kind,label=1)
    reply = f.message_type.add(name='Reply')
    reply.field.add(name='elems',number=1,type=11,label=3,type_name='.monitor.Elem')
    pool = descriptor_pool.DescriptorPool(); pool.Add(f)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName('monitor.Reply'))


def decode_segment(content, bvid, cid):
    from google.protobuf.message import DecodeError
    try:
        response = segment_message()(); response.ParseFromString(content)
    except DecodeError:
        raise ProviderError('弹幕分段解析失败，进度未推进') from None
    if content and not response.elems and response.SerializeToString() != b'':
        # Nonempty unknown-only messages are not evidence of a valid empty segment.
        raise ProviderError('弹幕分段缺少可识别字段，进度未推进')
    if len(response.elems) > 50000:
        raise ProviderError('单分段弹幕过多，任务已暂停')
    result = []
    for row in response.elems:
        identity = row.idStr or (str(row.id) if row.id else '')
        if not identity or row.progress < 0 or not row.content:
            raise ProviderError('弹幕身份或文本字段异常，进度未推进')
        result.append(DanmakuItem(bvid,cid,row.progress/1000,row.content,row.ctime,source_id=identity))
    return result


def comment(row, bvid, parent=None):
    identity = str(row.get('rpid_str') or row.get('rpid') or '')
    if not identity:
        raise ProviderError('评论缺少平台 ID，进度未推进')
    member = row.get('member') or {}
    return VideoComment(bvid,identity,parent, user_name=str(member.get('uname') or ''),
        message=str((row.get('content') or {}).get('message') or ''),
        like_count=int(row.get('like') or 0),reply_count=int(row.get('rcount') or 0),ctime=int(row.get('ctime') or 0))


class FullTextProvider:
    def __init__(self,client,auth):
        self.client=client; self.auth=auth; self.keys=None

    async def request(self,path,params=None,binary=False):
        return await self.client.authenticated_response(API+path,dict(self.auth.cookies),params,binary=binary)

    async def view(self,bvid):
        data=(await self.request('/x/web-interface/view',{'bvid':bvid})).get('data') or {}
        parts=[{'cid':int(p['cid']),'page':int(p['page']),'name':str(p.get('part') or ''),'duration':int(p['duration'])} for p in data.get('pages',[])]
        if not data.get('aid') or not parts or len(parts)>1000 or any(p['duration']<=0 for p in parts):
            raise ProviderError('视频分 P 信息异常')
        return int(data['aid']),parts

    async def keys_refresh(self):
        data=await self.auth.validate()
        images=data.get('wbi_img') or {}
        self.keys=tuple(urlsplit(images[k]).path.rsplit('/',1)[-1].split('.')[0] for k in ('img_url','sub_url'))

    async def roots(self,aid,offset):
        if not self.keys: await self.keys_refresh()
        params={'oid':aid,'type':1,'mode':2,'pagination_str':json.dumps({'offset':offset},separators=(',',':')),'plat':1,'web_location':1315875}
        return (await self.request('/x/v2/reply/wbi/main',sign(params,*self.keys))).get('data') or {}

    async def children(self,aid,root,page):
        return (await self.request('/x/v2/reply/reply',{'oid':aid,'type':1,'root':root,'pn':page,'ps':20})).get('data') or {}

    async def segment(self,bvid,cid,index):
        content=await self.request('/x/v2/dm/web/seg.so',{'type':1,'oid':cid,'segment_index':index},binary=True)
        return decode_segment(content,bvid,cid)
