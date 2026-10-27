"""Read-only image, task and delivery quantity reporting."""
import argparse
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


def summarize(run_dirs, delivery=None):
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
    unknown=max(0,len(intents)-len(tasks))
    result={'status':'counts_only_not_visual_approval','runs':runs,
            'generation_attempts_recorded':len(intents),'confirmed_generation_tasks':len(tasks),
            'unconfirmed_attempts':unknown,'generated_image_count':len(images),
            'final_delivered_image_count':len(delivered) if delivery else None,
            'repair_generation_tasks':sum(t['stage']=='repair' for t in tasks.values()),
            'preview_generation_tasks':sum(t['kind']=='master' for t in tasks.values()),
            'tasks':list(tasks.values()),'generated_images':list(images.values()),'delivered_images':delivered,
            'image_count_complete':not warnings and unknown==0,
            'warnings':sorted(set(warnings)),'new_generation_calls':0}
    return result


def human_summary(result):
    """User-facing delivery counts, without financial fields."""
    text=(f"最终交付：{result['final_delivered_image_count']} 张\n累计已保存生成图片：{result['generated_image_count']} 张（含候选及返修）\n"
          f"已确认生成任务：{result['confirmed_generation_tasks']} 次；其中返修 {result['repair_generation_tasks']} 次、预览 {result['preview_generation_tasks']} 次\n")
    if result['unconfirmed_attempts']:
        text+=f"提交结果未确认：{result['unconfirmed_attempts']} 次\n"
    if not result['image_count_complete']:
        text+='图片统计尚不完整：存在结果未确认或文件不可读，详见 JSON。\n'
    return text


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,nargs='+',required=True)
    p.add_argument('--delivery',type=Path,required=True,help='Final reviewed originals: images with id/path/sha256')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        check(not a.output.exists(),'Preserve existing accounting; use a new output folder')
        result=summarize(a.runs,a.delivery)
        a.output.mkdir(parents=True)
        (a.output/'usage-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        text=human_summary(result)
        (a.output/'交付统计.txt').write_text(text,encoding='utf-8');print(text)
    except (ValueError,OSError,KeyError,TypeError) as exc:p.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
