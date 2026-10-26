"""Read-only image/attempt accounting and evidenced star-coin reconciliation."""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from PIL import Image
from starcanvas_adapter import read,sha,path_key,check


def run_usage(folder):
    folder=Path(folder).resolve();state=read(folder/'state.json');package=read(folder/'package.json')
    check(sha(folder/'package.json')==state['package_sha256'],'Usage package differs from frozen run')
    by_id={t['id']:t for t in package['tasks']};records=[];images={};warnings=[];intents=[]
    for batch in state.get('batches',[]):
        for sid in batch['local_ids']:intents.append((state['run_id'],batch['id'],sid))
    for sid,local in state.get('tasks',{}).items():
        tid=local.get('task_id')
        if not tid:continue
        task=by_id[sid];records.append({'task_id':tid,'page_id':sid,'kind':task['kind'],
            'stage':package['ready_stage'],'status':local['status'],'model_id':task['model_id']})
        snapshot=folder/'tasks'/(sid+'.json')
        if not snapshot.is_file():
            warnings.append(tid+': task output snapshot unavailable');continue
        remote=read(snapshot)
        check(remote.get('id')==tid and remote.get('projectId')==state['project_id']
              and remote.get('runTargetId')==local['node_id'],'Usage task identity mismatch')
        inputs={r['sha256'] for r in task['references']}
        for row in remote.get('outputs',{}).get('generated',[]):
            if row.get('source')!='generated':continue
            p=Path(row.get('path',''))
            check(p.resolve().parent==Path(task['output_dir']).resolve(),'Usage output outside recorded task directory')
            check(row.get('taskId',tid)==tid and row.get('nodeId',local['node_id'])==local['node_id'],'Usage output identity mismatch')
            try:
                digest=sha(p)
                if digest in inputs:continue
                with Image.open(p) as im:im.load()
            except (OSError,ValueError):
                warnings.append(tid+': generated image unavailable or undecodable');continue
            images[(tid,path_key(p))]={'task_id':tid,'path':str(p.resolve()),'sha256':digest}
    return {'run_path':str(folder),'run_id':state['run_id'],'intent_keys':intents,'tasks':records,
            'images':list(images.values()),'warnings':sorted(set(warnings))}


def amount(value):
    check(isinstance(value,(int,float,str)) and not isinstance(value,bool),'Star coins must be numeric')
    try:n=Decimal(str(value))
    except InvalidOperation:raise ValueError('Invalid star coins') from None
    check(n.is_finite() and n>=0,'Star coins must be finite and nonnegative')
    return n


def summarize(run_dirs, delivery=None, billing=None):
    folders=[];seen=set()
    def add(folder):
        root=Path(folder).resolve();key=path_key(root)
        if key in seen:return
        seen.add(key);folders.append(root)
        package=read(root/'package.json')
        if package.get('repair_canvas_version')==1:
            from repair_canvas import context
            add(context(package)['source_run'])
        if (root/'fallback-chain.json').is_file():
            chain=read(root/'fallback-chain.json')
            for entry in chain['attempts']:
                child=Path(entry['folder']).resolve();tier=entry['tier']
                check(type(tier) is int and tier in (0,1,2) and (child==root or child==root/('fallback-'+str(tier))),
                      'Invalid usage fallback path')
                if (child/'state.json').is_file():add(child)
    for folder in run_dirs:add(folder)
    check(folders,'At least one run required')
    tasks={};images={};intents=set();warnings=[];runs=[]
    for folder in folders:
        usage=run_usage(folder);runs.append({'path':str(folder),'run_id':usage['run_id']})
        intents.update(tuple(k) for k in usage['intent_keys']);warnings.extend(usage['warnings'])
        for t in usage['tasks']:
            check(t['task_id'] not in tasks or tasks[t['task_id']]==t,'Conflicting duplicated task in usage')
            tasks[t['task_id']]=t
        for im in usage['images']:images[(im['task_id'],path_key(im['path']))]=im
    delivered=[]
    if delivery:
        manifest=Path(delivery).resolve();items=read(manifest).get('images')
        check(isinstance(items,list) and items,'Delivery requires final images list after visual review')
        keys=set();ids=set();generated_hashes={im['sha256'] for im in images.values()}
        for item in items:
            p=(manifest.parent/Path(item['path'])).resolve();sid=item['id'];key=path_key(p)
            check(isinstance(sid,str) and sid and sid not in ids and key not in keys,'Duplicate final page ID/path')
            check(p.is_file() and sha(p)==item.get('sha256'),'Final delivery image changed/missing')
            check(item['sha256'] in generated_hashes,'Final delivery image is not from the supplied runs')
            ids.add(sid);keys.add(key);delivered.append({'id':sid,'path':str(p),'sha256':item['sha256']})
    charged={};billing_evidence=None
    if billing:
        path=Path(billing).resolve();ledger=read(path)
        check(ledger.get('currency')=='star_coin' and ledger.get('kind')=='actual_platform_bill',
              'Only actual platform star-coin bills are accepted, never estimates or balance differences')
        ev=ledger.get('evidence',{});source=(path.parent/Path(ev.get('path',''))).resolve()
        check(source!=path,'Normalized ledger cannot be its own original billing evidence')
        check(source.is_file() and sha(source)==ev.get('sha256'),'Original billing evidence missing or changed')
        billing_evidence={'path':str(source),'sha256':ev['sha256'],'ledger_sha256':sha(path)}
        check(isinstance(ledger.get('records'),list),'Billing records required')
        for row in ledger['records']:
            tid=row.get('task_id')
            check(tid in tasks and tid not in charged,'Unknown or duplicated billed task')
            debit=amount(row.get('charged_star_coins'));refund=amount(row.get('refunded_star_coins',0))
            check(refund<=debit,'Refund exceeds charged amount')
            charged[tid]=debit-refund
    unknown=max(0,len(intents)-len(tasks));missing=sorted(set(tasks)-set(charged))
    complete=not missing and unknown==0
    total=sum(charged.values(),Decimal(0))
    result={'status':'accounting_only_not_visual_approval','runs':runs,
            'generation_attempts_recorded':len(intents),'confirmed_generation_tasks':len(tasks),
            'unconfirmed_attempts':unknown,'generated_image_count':len(images),
            'final_delivered_image_count':len(delivered) if delivery else None,
            'repair_generation_tasks':sum(t['stage']=='repair' for t in tasks.values()),
            'preview_generation_tasks':sum(t['kind']=='master' for t in tasks.values()),
            'star_coins_status':'verified' if complete else 'pending_verification',
            'actual_star_coins':str(total) if complete else None,
            'verified_partial_star_coins':str(total) if charged else None,
            'unbilled_task_ids':missing,'billing_evidence':billing_evidence,
            'tasks':list(tasks.values()),'generated_images':list(images.values()),'delivered_images':delivered,
            'image_count_complete':not warnings and unknown==0,
            'warnings':sorted(set(warnings)),'new_generation_calls':0}
    return result


def human_summary(result):
    """User-facing counts; show cost only when the complete actual total is verified."""
    text=(f"最终交付：{result['final_delivered_image_count']} 张\n累计已保存生成图片：{result['generated_image_count']} 张（含候选及返修）\n"
          f"已确认生成任务：{result['confirmed_generation_tasks']} 次；其中返修 {result['repair_generation_tasks']} 次、预览 {result['preview_generation_tasks']} 次\n")
    if result['unconfirmed_attempts']:
        text+=f"提交结果未确认：{result['unconfirmed_attempts']} 次\n"
    if result['star_coins_status']=='verified' and result['actual_star_coins'] is not None:
        text+=f"实际净消耗：{result['actual_star_coins']} 星币\n"
    if not result['image_count_complete']:
        text+='图片统计尚不完整：存在结果未确认或文件不可读，详见 JSON。\n'
    return text


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,nargs='+',required=True)
    p.add_argument('--delivery',type=Path,required=True,help='Final reviewed originals: images with id/path/sha256')
    p.add_argument('--billing',type=Path,help='Normalized actual bill with original evidence; omit if unavailable')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        check(not a.output.exists(),'Preserve existing accounting; use a new output folder')
        result=summarize(a.runs,a.delivery,a.billing)
        a.output.mkdir(parents=True)
        (a.output/'usage-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        text=human_summary(result)
        name='费用统计.txt' if result['star_coins_status']=='verified' and result['actual_star_coins'] is not None else '交付统计.txt'
        (a.output/name).write_text(text,encoding='utf-8');print(text)
    except (ValueError,OSError,KeyError,TypeError) as exc:p.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
