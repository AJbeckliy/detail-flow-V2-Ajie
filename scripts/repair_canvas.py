"""Bind repair runs to their source canvas; create new nodes, never edit source nodes."""
import copy
import math
from pathlib import Path
from starcanvas_adapter import read,sha,check,evidence,path_key


def context(manifest):
    raw=manifest.get('repair_context')
    check(isinstance(raw,dict) and evidence(raw.get('source_run')),'Repair requires repair_context.source_run for the original canvas')
    folder=Path(raw['source_run']).resolve()
    check((folder/'state.json').is_file() and (folder/'package.json').is_file(),'Original repair run is missing')
    state=read(folder/'state.json');package=read(folder/'package.json');digest=sha(folder/'package.json')
    check(digest==state.get('package_sha256'),'Original repair package changed')
    check(evidence(state.get('project_id')) and evidence(state.get('run_id')),'Original canvas/run identity missing')
    expected={t['id']:t for t in package['tasks']}
    issues=raw.get('issues')
    ids={t['id'] for t in manifest['tasks']}
    check(isinstance(issues,dict) and set(issues)==ids and all(evidence(x) and len(x)<=200 for x in issues.values()),
          'Record one concise actual repair reason per task, at most 200 characters')
    previous=package.get('repair_context',{}).get('round',0)
    number=raw.get('round',previous+1)
    check(type(number) is int and number>previous,'Repair round must advance beyond its source run')
    nodes={}
    for task in manifest['tasks']:
        sid=task['id'];original=expected.get(sid)
        check(original and original['kind']==task['kind'],'Repair task does not match a source page/kind')
        check(task.get('page_id',sid.removeprefix('screen-'))==original.get('page_id',sid.removeprefix('screen-')),
              'Repair page differs from its source page')
        mapping=state.get('id_map',{})
        node={k:mapping.get(original[k+'_ref']) for k in ('load','gen','workshop')}
        check(all(evidence(v) for v in node.values()) and len(set(node.values()))==3,'Original page node mapping unavailable')
        nodes[sid]=node
    result={'source_run':str(folder),'source_run_id':state['run_id'],'source_package_sha256':digest,
            'project_id':state['project_id'],'round':number,'issues':copy.deepcopy(issues),'source_nodes':nodes}
    if 'repair_canvas_version' in manifest:
        check(manifest['repair_canvas_version']==1 and raw==result,'Frozen repair canvas binding changed')
    return result


def placed_operations(package,snapshot,run_id):
    binding=context(package)
    nodes=snapshot.get('canvas',{}).get('nodes')
    check(isinstance(nodes,list),'Original canvas nodes unavailable')
    actual={n['id']:dict(n,**n.get('data',{})) for n in nodes}
    check(len(actual)==len(nodes),'Duplicate source canvas node IDs')
    for page in binding['source_nodes'].values():
        for key,typ in (('load','image/load-image-grid'),('gen','ai-image/gpt-image'),('workshop','image/workshop')):
            check(actual.get(page[key],{}).get('type')==typ,'Original source node missing or wrong type; do not create another canvas')
    def number(value,default=0):
        return float(value) if type(value) in (int,float) and math.isfinite(value) else default
    right=max((number(n.get('x'))+max(1000,number(n.get('width',n.get('w')),1000)) for n in actual.values()),default=0)
    ops=copy.deepcopy(package['operations'])
    positions={}
    for t in package['tasks']:
        source=actual[binding['source_nodes'][t['id']]['load']]
        for index,key in enumerate(('load','gen','workshop')):
            positions[t[key+'_ref']]=(right+1000+index*1200,number(source.get('y')))
        positions[t['note_ref']]=(right+400,number(source.get('y')))
    for op in ops:
        if op['op']=='createNode':
            op['x'],op['y']=positions[op['clientRef']]
            if op['type']=='text/note':op['data']['content']+='\n本轮记录：'+run_id[:8]
    return ops,set(actual)


def trace(package,state):
    binding=context(package);source=read(Path(binding['source_run'])/'state.json')
    result={'project_id':state['project_id'],'round':binding['round'],'source_run':binding['source_run'],
            'source_run_id':binding['source_run_id'],'run_id':state['run_id'],'pages':[]}
    for t in package['tasks']:
        sid=t['id'];original=source.get('tasks',{}).get(sid,{})
        result['pages'].append({'page_id':t.get('page_id',sid.removeprefix('screen-')),'task_id':sid,
            'reason':binding['issues'][sid],'source_nodes':binding['source_nodes'][sid],
            'source_remote_task_id':original.get('task_id'),'source_return_path':original.get('return_path'),
            'repair_nodes':{k:state['id_map'][t[k+'_ref']] for k in ('load','gen','workshop')},
            'note_node_id':state['id_map'].get(t.get('note_ref')),
            'prompt_path':t['prompt_path'],'prompt_sha256':t['prompt_sha256'],
            'output_dir':t['output_dir']})
    return result
