"""Provider-neutral image transport. Agent matches documented protocols first."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import quote, urlparse
import uuid


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def key(config):
    value = os.environ.get(config['key_env'])
    if not value:
        raise ValueError('API Key 未配置')
    return value


def endpoint(config, name, task_id=None):
    path = config['paths'][name]
    if task_id is not None:
        path = path.replace('{id}', quote(task_id, safe=''))
    return config['base_url'].rstrip('/') + '/' + path.lstrip('/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(config, name, body=None, mime='application/json', task_id=None):
    req = urllib.request.Request(endpoint(config, name, task_id), data=body,
        headers={'Authorization':'Bearer '+key(config), 'Content-Type':mime,
                 'User-Agent':config.get('user_agent','DetailFlow/1.0')})
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
        return json.load(response)


def validate(config):
    ua=config.get('user_agent','DetailFlow/1.0')
    if not isinstance(ua,str) or not ua.strip() or '\r' in ua or '\n' in ua:
        raise ValueError('User-Agent 配置无效')
    url = urlparse(config.get('base_url', ''))
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('API 地址必须是无凭据和查询参数的 HTTPS 地址')
    if config.get('protocol') not in ('images_sync_v1','images_async_v1'):
        raise ValueError('接口类型不匹配')
    if not config.get('model') or not config.get('key_env'):
        raise ValueError('模型或密钥配置缺失')
    evidence = config.get('evidence', {})
    if not (evidence.get('source') and evidence.get('notes') and evidence.get('reference_images') is True and evidence.get('model') == config['model']):
        raise ValueError('尚未确认所选模型的参考图接口能力')
    required = ['check','generate'] + (['edit'] if config['protocol']=='images_sync_v1' else ['upload','status'])
    for name in required:
        path = config.get('paths', {}).get(name, '')
        if not path or path.startswith('/') or any(c in path for c in (':','?','#','\\','..','%')):
            raise ValueError('接口路径必须是经文档确认的相对路径')
    if config['protocol']=='images_async_v1' and '{id}' not in config['paths']['status']:
        raise ValueError('缺少任务查询模板')
    if config['protocol']=='images_sync_v1' and config.get('image_field') not in ('image','image[]'):
        raise ValueError('图片输入字段不匹配')
    if config.get('check_kind') not in ('models','account'):
        raise ValueError('没有支持的只读鉴权检查方式')
    for name in ('max_images','max_image_bytes'):
        if type(config.get(name)) is not int or config[name] <= 0:
            raise ValueError('缺少经核实的图片限制')
    formats=config.get('image_formats')
    if not isinstance(formats,list) or not formats or not set(formats)<= {'png','jpeg','webp'}:
        raise ValueError('缺少经文档确认的参考图格式')
    if not isinstance(config.get('parameters'), dict):
        raise ValueError('缺少参数能力记录')
    if set(config['parameters']) & {'model','prompt','images','image','n','stream','headers','api_key'}:
        raise ValueError('参数不能覆盖身份、输入或协议字段')


def check(config, receipt):
    # Invalidate a previous passing receipt before any checks.
    save(receipt, {'status':'not_ready'})
    validate(config)
    result = request(config, 'check')
    code = result.get('code')
    code_ok = (code is None or code is True or (type(code) is int and code in (0,200))
               or (type(code) is str and code in ('0','200','success','SUCCESS')))
    if (result.get('error') or result.get('success') is False or result.get('status') is False
            or not code_ok
            or result.get('status') in ('error', 'failed', 'FAILURE')):
        raise ValueError('只读鉴权检查失败')
    data = result.get('data')
    if config['check_kind']=='models':
        if not isinstance(data,list) or config['model'] not in [x.get('id') for x in data if isinstance(x,dict)]:
            raise ValueError('模型不可用或模型列表不匹配')
    elif not isinstance(data,dict) or not data:
        raise ValueError('只读账户响应不匹配')
    save(receipt, {'status':'ready','config_hash':digest(config),'key_hash':digest(key(config)),
                   'generation_verified':False})
    return '接口兼容检查通过；实际出图尚未验证'


def multipart(fields, files):
    boundary=uuid.uuid4().hex
    chunks=[]
    for name,value in fields.items():
        chunks.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+str(value)+'\r\n').encode())
    for name,path in files:
        p=Path(path)
        mime = {'.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp'}[p.suffix.lower()]
        chunks.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"; filename="image'+p.suffix.lower()+'"\r\nContent-Type: '+mime+'\r\n\r\n').encode()+p.read_bytes()+b'\r\n')
    return b''.join(chunks)+('--'+boundary+'--\r\n').encode(), 'multipart/form-data; boundary='+boundary


def submit(config, receipt, payload, folder, execute=False):
    validate(config)
    if receipt.get('status')!='ready' or receipt.get('config_hash')!=digest(config) or receipt.get('key_hash')!=digest(key(config)):
        raise ValueError('配置或 Key 已变化，必须重新检查')
    if not isinstance(payload.get('prompt'),str) or not payload['prompt'].strip():
        raise ValueError('提示词不能为空')
    if set(payload)-{'prompt','images','parameters'}:
        raise ValueError('请求存在未支持字段')
    images=payload.get('images',[])
    if not isinstance(images,list) or len(images)>config['max_images']:
        raise ValueError('参考图数量不匹配')
    for image in images:
        p=Path(image)
        if not p.is_absolute() or p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp') or not p.is_file() or p.stat().st_size>config['max_image_bytes']:
            raise ValueError('参考图路径、格式或大小不匹配')
        from PIL import Image
        with Image.open(p) as im:
            if (im.format or '').lower() not in config['image_formats']:
                raise ValueError('所选模型不支持该参考图格式')
            actual_suffix={'.png':'png','.jpg':'jpeg','.jpeg':'jpeg','.webp':'webp'}[p.suffix.lower()]
            if im.format.lower()!=actual_suffix:
                raise ValueError('图片实际格式与扩展名不一致')
            limits=config.get('image_dimensions',{})
            if any(im.size[i]<limits.get('min_'+axis,1) or im.size[i]>limits.get('max_'+axis,float('inf')) for i,axis in enumerate(('width','height'))):
                raise ValueError('参考图尺寸不符合模型要求')
            im.verify()
    params=payload.get('parameters',{})
    if not isinstance(params,dict):
        raise ValueError('参数必须是对象')
    for name,value in params.items():
        if name not in config['parameters'] or value not in config['parameters'][name]:
            raise ValueError('参数未通过兼容检查')
    if not execute:
        return '本地检查通过；未上传或生成'
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    save(folder/'config.json',config);save(folder/'request.json',payload)
    save(folder/'state.json',{'status':'preparing'})
    body=dict(params,model=config['model'],prompt=payload['prompt'],n=1)
    if config['protocol']=='images_async_v1':
        urls=[]
        for image in images:
            blob,mime=multipart({},[('file',image)])
            uploaded=request(config,'upload',blob,mime)
            if urlparse(uploaded.get('url','')).scheme not in ('https','http'):
                raise ValueError('上传响应不匹配')
            urls.append(uploaded['url']);save(folder/'uploads.json',urls)
        body['images']=urls
        blob=json.dumps(body).encode();mime='application/json';route='generate'
    elif images:
        blob,mime=multipart(body,[(config['image_field'],p) for p in images]);route='edit'
    else:
        blob=json.dumps(body).encode();mime='application/json';route='generate'
    save(folder/'state.json',{'status':'submission_uncertain'})
    response=request(config,route,blob,mime)
    save(folder/'submission.json',response)
    if config['protocol']=='images_async_v1':
        task=response.get('id') or response.get('task_id')
        if not isinstance(task,str) or not task:
            raise ValueError('提交结果不确定；禁止自动重发')
        state={'status':'submitted','task_id':task}
    else:
        if not isinstance(response.get('data'),list) or len(response['data'])!=1 or not (response['data'][0].get('url') or response['data'][0].get('b64_json')):
            raise ValueError('出图响应不匹配；禁止自动重发')
        state={'status':'SUCCESS'}
    save(folder/'state.json',state)
    return '响应已保存；仍需取图和视觉审核'


def status(folder):
    folder=Path(folder);config=read(folder/'config.json');state=read(folder/'state.json')
    if config['protocol']=='images_sync_v1':
        return state['status']
    task=state.get('task_id')
    if not task:
        raise ValueError('无任务编号，须核对提交结果，不能自动重发')
    result=request(config,'status',task_id=task)
    save(folder/'query.json',result)
    current=result.get('data',{}).get('status','unknown_response')
    if current in ('NOT_START','SUBMITTED','IN_PROGRESS','SUCCESS','FAILURE'):
        save(folder/'state.json',dict(state,status=current))
    return current


def download(folder):
    folder=Path(folder);config=read(folder/'config.json')
    if config['protocol']=='images_async_v1':
        data=read(folder/'query.json').get('data',{})
        if data.get('status')!='SUCCESS':
            raise ValueError('任务尚未成功')
        item={'url':data.get('result_url')}
    else:
        if read(folder/'state.json').get('status')!='SUCCESS':
            raise ValueError('任务尚未成功')
        item=read(folder/'submission.json')['data'][0]
    if (folder/'collection.json').exists():
        recorded=read(folder/'collection.json');p=folder/recorded['file']
        if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==recorded['sha256']:
            return '原图已保存，仍需审核'
    if item.get('b64_json'):
        raw=base64.b64decode(item['b64_json'],validate=True)
    else:
        if urlparse(item.get('url','')).scheme!='https':
            raise ValueError('结果不是 HTTPS 图片链接')
        # Deliberately no API key on the media request.
        media_request = urllib.request.Request(item['url'], headers={
            'User-Agent': config.get('user_agent', 'DetailFlow/1.0')})
        with urllib.request.urlopen(media_request,timeout=60) as response:
            raw=response.read()
    if raw.startswith(b'\x89PNG\r\n\x1a\n'): suffix='.png'
    elif raw.startswith(b'\xff\xd8\xff'): suffix='.jpg'
    elif raw[:4]==b'RIFF' and raw[8:12]==b'WEBP': suffix='.webp'
    else: raise ValueError('返回内容不是支持的图片；不能重新生成')
    p=folder/('original'+suffix)
    if p.exists():
        if p.read_bytes() != raw:
            raise ValueError('已有原图与返回结果不同，须核对，不能覆盖')
    else:
        temp=folder/('original'+suffix+'.partial')
        temp.write_bytes(raw)
        temp.replace(p)
    save(folder/'collection.json',{'file':p.name,'sha256':hashlib.sha256(raw).hexdigest()})
    return '原图已保存；仍需解码、尺寸和视觉审核'


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('check');p.add_argument('config');p.add_argument('receipt')
    p=sub.add_parser('submit');p.add_argument('config');p.add_argument('receipt');p.add_argument('request');p.add_argument('folder');p.add_argument('--execute',action='store_true')
    for name in ('status','download'):sub.add_parser(name).add_argument('folder')
    a=parser.parse_args()
    try:
        if a.command=='check':result=check(read(a.config),a.receipt)
        elif a.command=='submit':result=submit(read(a.config),read(a.receipt),read(a.request),a.folder,a.execute)
        elif a.command=='status':result=status(a.folder)
        else:result=download(a.folder)
        print(result)
    except urllib.error.HTTPError as exc:
        print('这个 API 地址目前无法用于本次操作：HTTP',exc.code,'；请检查鉴权、路径或服务状态。禁止自动重新提交。')
        raise SystemExit(1)
    except ValueError as exc:
        print('这个 API 地址目前无法用于本次操作：',str(exc))
        raise SystemExit(1)
    except Exception as exc:
        print('操作未完成：',type(exc).__name__,'。请核对连接和本地记录；不自动重新提交。')
        raise SystemExit(1)


if __name__=='__main__':main()
