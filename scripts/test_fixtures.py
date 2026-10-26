"""Synthetic Starcanvas execution-row fixture shared by offline regression tests."""
from pathlib import Path
import json
import hashlib
import copy


def bind_repair_fixture(manifest,root):
    """Local source-run identity for compiler-only tests; never a live project."""
    folder=Path(root)/'synthetic-source-run';folder.mkdir(exist_ok=True)
    tasks=copy.deepcopy(manifest['tasks']);mapping={}
    for t in tasks:
        for key in ('load','gen','workshop'):
            t[key+'_ref']=t['id']+'-'+key;mapping[t[key+'_ref']]='fixture-'+t['id']+'-'+key
    p=folder/'package.json';p.write_text(json.dumps({'tasks':tasks}),encoding='utf-8')
    (folder/'state.json').write_text(json.dumps({'project_id':'fixture-original-project','run_id':'fixture-original-run',
        'package_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'id_map':mapping}),encoding='utf-8')
    manifest['repair_context']={'source_run':str(folder),'issues':{t['id']:'Offline repair fixture' for t in tasks}}


def bind_review_fixture(manifest,root):
    """Declare the planned copy before a test mutates it; never used in production."""
    pages=[]
    for task in manifest['tasks']:
        pid=task['id'].removeprefix('screen-')
        if task['kind']=='master':task['page_ids']=[pid]
        else:task['page_id']=pid
        pages.append({'slice_id':pid,'text_exact':{'body':Path(task['prompt_path']).read_bytes().decode('utf-8').rstrip('\r\n')}})
    path=Path(root)/'approved-fixture-plan.json'
    path.write_text(json.dumps({'pages':pages},ensure_ascii=False),encoding='utf-8')
    manifest['approved_plan']={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                               'approval_evidence':'Synthetic offline reviewed revision; never paid authority'}


def workshop_fixture(task):
    return {'autoSaveEnabled':True,'rows':[{
        'id':'fixture-row','prompt':Path(task['prompt_path']).read_bytes().decode('utf-8'),
        'images':[r['path'] for r in task['references']],
        'params':{'model':task['model_id'],'resolution':task['resolution'],
                  'aspectRatio':task['aspect_ratio'],'quality':task.get('quality','auto'),
                  'gptStyle':task.get('gpt_style','sunburst'),'transparent':False},
        'saveDir':task['output_dir'],'saveFilled':True
    }]}
