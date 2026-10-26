"""Deterministic Starcanvas batch execution. No prompt authoring or automatic retries."""
import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

from starcanvas_adapter import (LOCKED_PROFILE, ENTERPRISE_PROFILE, assert_readback, check, extract_readback, transport_prompt,
                                path_key, read, reconcile, sha, task_profile, validate)
from starcanvas_mcp import StdioMCP, ToolError, TransportError, load_connection
from starcanvas_startup import ready_client
from skill_release import verify as verify_release

FINAL = {'verified', 'selection_required', 'failed', 'output_invalid', 'submission_rejected', 'collection_pending'}
ACTIVE = {'running', 'queued', 'awaiting_output', 'submission_unknown'}
REQUIRED = {'project_create','project_export','workflow_apply_patch','canvas_attach_local_images',
            'run_preflight','canvas_run_node','task_get','task_list','model_get_capabilities','canvas_get_summary','canvas_get_node','canvas_prepare_run'}


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


@contextmanager
def run_lock(folder):
    """OS lock releases after a crash; no stale lock-file deletion is needed."""
    file=(Path(folder)/'executor.lock').open('a+b')
    if file.tell()==0:file.write(b'0');file.flush()
    file.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        file.close();raise ValueError('Another executor owns this run; use status, not another submit')
    try:yield
    finally:
        file.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(file.fileno(),fcntl.LOCK_UN)
        file.close()


def canonical_operations(tasks):
    operations=[]
    for i,t in enumerate(tasks):
        sid=t['id']
        check((t['load_ref'],t['gen_ref'],t['workshop_ref'])==(sid+'-load',sid+'-gen',sid+'-workshop'),
              'Compiled node references changed')
        operations.extend([
            {'op':'createNode','clientRef':t['load_ref'],'type':'image/load-image-grid','x':0,'y':i*560},
            {'op':'createNode','clientRef':t['gen_ref'],'type':'ai-image/gpt-image','x':360,'y':i*560,
             'data':{'prompt':transport_prompt(t),'modelType':t['model_id'],
                     'resolution':t['resolution'],'aspectRatio':t['aspect_ratio'],'quality':t.get('quality','auto')}},
            {'op':'createNode','clientRef':t['workshop_ref'],'type':'image/workshop','x':720,'y':i*560},
            {'op':'connect','fromRef':t['load_ref'],'fromPort':'imageGroup','toRef':t['gen_ref'],'toPort':'image'},
            {'op':'connect','fromRef':t['gen_ref'],'fromPort':'image','toRef':t['workshop_ref'],'toPort':'image'}])
    for i,t in enumerate(tasks):
        if t.get('canvas_note'):
            check(t.get('note_ref')==t['id']+'-trace-note','Compiled trace note reference changed')
            operations.append({'op':'createNode','clientRef':t['note_ref'],'type':'text/note','x':-600,'y':i*560,
                               'data':{'content':t['canvas_note']}})
    return operations


def verify_package(package):
    check(package.get('workflow') in ('detail-flow-copy-led-v2','detail-flow-direct-v3') and package.get('execution_profile') in (LOCKED_PROFILE,ENTERPRISE_PROFILE),
          'Executor requires a newly compiled current-profile package, not a legacy/experimental package')
    # Old immutable packages remain resumable; every new CLI compilation is bound.
    validate(package,require_review_binding='review_binding_version' in package,
             require_repair_authorization='repair_authorization_version' in package,
             require_repair_canvas='repair_canvas_version' in package)
    check(package.get('operations')==canonical_operations(package['tasks']),'Compiled operations changed; recompile from approved prompts')
    paths=[path_key(t['output_dir']) for t in package['tasks']]
    check(len(paths)==len(set(paths)),'Tasks cannot share an output directory')
    for t in package['tasks']:
        check(Path(t['output_dir']).is_absolute(),'Output directories must be absolute')
        check(t.get('prompt_sha256')==sha(t['prompt_path']),'Compiled prompt changed')
        check(t.get('workshop_settings')==dict(task_profile(t,package['execution_profile']),aspectRatio=t['aspect_ratio']),'Compiled stage settings changed')


def project_name(package,run_id):
    tasks=package['tasks'];stage=package['ready_stage']
    ratios={t['aspect_ratio'] for t in tasks}
    ratio_label=next(iter(ratios)).replace(':','比') if len(ratios)==1 else '多比例'
    if stage=='repair':
        ids=[t['id'][7:] if t['id'].startswith('screen-') else t['id'] for t in tasks]
        label='返修·'+('、'.join(ids) if len(ids)<=6 else '、'.join(ids[:6])+'等')
    elif all(t['kind']=='master' for t in tasks):
        tier=tasks[0].get('master_fallback_tier',0)
        label='预览·'+ratio_label+'·稳定' if package.get('execution_profile')==LOCKED_PROFILE else {0:'母版·9比21',1:'母版·9比21·降级1K',2:'母版·9比16·降级稳定'}[tier]
    elif stage=='production':label='正式页·'+ratio_label
    else:label={'sample':'分阶段试图','remaining':'分阶段剩余页'}.get(stage,stage)
    return 'DetailFlow·'+label+'·'+str(len(tasks))+'张·'+run_id[:8]


def doctor(client):
    release=verify_release(Path(__file__).resolve().parents[1])
    guide=client.resource('canvas://guide/workflow')
    context=client.call('workspace_get_context',{})
    names={t.get('name') for t in client.tools()}
    check(REQUIRED<=names,'Missing required Starcanvas tools: '+', '.join(sorted(REQUIRED-names)))
    return {'server':getattr(client,'server',{}).get('serverInfo',{}),'guide_sha256':hashlib.sha256(guide.encode()).hexdigest(),
            'skill_revision':release['revision'],'skill_content_sha256':release['content_sha256'],'release_sealed':release['sealed'],
            'tool_count':len(names),'required_tools_present':True,'workspace_read':context.get('ok') is True,'paid_calls':0}


def run_status(folder):
    """Read the selected attempt without hiding the original failure."""
    root=Path(folder).resolve();state=read(root/'state.json')
    result={'status':state['status'],'tasks':state.get('tasks',{}),'state_path':str(root/'state.json')}
    if (root/'fallback-chain.json').exists():
        chain=read(root/'fallback-chain.json');entry=chain['attempts'][-1];tier=entry['tier']
        check(type(tier) is int and 0<=tier<=2,'Invalid fallback status tier')
        selected=Path(entry['folder']).resolve()
        check(selected==root or selected==root/('fallback-'+str(tier)),'Invalid fallback status path')
        child=read(selected/'state.json') if (selected/'state.json').exists() else {'status':'preparing','tasks':{}}
        result.update(status=child['status'],tasks=child.get('tasks',{}),state_path=str(selected/'state.json'),
                      root_attempt_status=state['status'],selected_tier=tier,attempt_count=len(chain['attempts']))
    return result


class Executor:
    def __init__(self,client,folder,clock=None,sleep=None,progress=None):
        self.client=client;self.folder=Path(folder).resolve()
        self.clock=clock or time.time;self.sleep=sleep or time.sleep;self.progress=progress or (lambda value:None)
        self.state_path=self.folder/'state.json'
        self.state=read(self.state_path) if self.state_path.exists() else None
        self.package=read(self.folder/'package.json') if (self.folder/'package.json').exists() else None
        self.bootstrapped=False

    def bootstrap(self):
        if not self.bootstrapped:
            self.state['connection_check']=doctor(self.client);self.bootstrapped=True

    def save(self):
        self.state['updated_at_ms']=round(self.clock()*1000)
        atomic_json(self.state_path,self.state)

    def event(self,event,**values):
        row={'at_ms':round(self.clock()*1000),'event':event,**values}
        with (self.folder/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')

    def call(self,name,args):
        begin=self.clock()
        try:
            result=self.client.call(name,args)
            check(isinstance(result,dict) and result.get('ok') is True,f'{name} returned an unsuccessful envelope')
        except (ToolError,TransportError,ValueError):
            self.event('rpc_failed',tool=name,elapsed_ms=round((self.clock()-begin)*1000));raise
        self.event('rpc',tool=name,elapsed_ms=round((self.clock()-begin)*1000))
        revision=result.get('meta',{}).get('revision')
        if isinstance(revision,int) and not isinstance(revision,bool):self.state['revision']=revision
        return result.get('data',{})

    def checked_mutation(self,name,args,key=None):
        args=dict(args,projectId=self.state['project_id'],expectedRevision=self.state['revision'])
        preview=self.call(name,dict(args,dryRun=True))
        check(not preview.get('blocked') and not any(i.get('severity')=='error' for i in preview.get('issues',[])),
              'Mutation preview blocked')
        commit=dict(args,dryRun=False)
        if key:commit['idempotencyKey']=self.state['run_id']+'-'+key
        result=self.call(name,commit)
        self.save()
        return result

    def snapshot(self,label):
        path=self.folder/'snapshots'/(label+'-'+uuid.uuid4().hex+'.json');path.parent.mkdir(exist_ok=True)
        self.call('project_export',{'kind':'batch','projectId':self.state['project_id'],'path':str(path)})
        check(path.is_file(),'Snapshot not visible on this filesystem; server and executor must share files')
        return read(path),path

    def verify_snapshot(self):
        snapshot,path=self.snapshot('verified')
        if self.state.get('node_notes') and self.state['status']=='preparing':
            nodes={n['id']:dict(n,**n.get('data',{})) for n in snapshot['canvas']['nodes']}
            for nid,content in self.state['node_notes'].items():
                check(nodes.get(nid,{}).get('content')==content,'Canvas trace note changed or missing')
        rb=extract_readback(self.package,snapshot,self.state['id_map'])
        preparations=self.state.get('preparations',{})
        for t in self.package['tasks']:
            sid=t['id'];item=preparations.get(sid,{})
            node=rb['workshops'][sid];row=node['rows'][0];binding=node.get('runPreparation',{})
            check(item.get('ready') is True and len(item.get('rows',[]))==1,f'{sid}: missing prepared request')
            prepared_row=item['rows'][0];request=prepared_row.get('effectiveRequest',{})
            check(binding.get('id')==item.get('preparationId') and binding.get('digest')==item.get('requestDigest')
                  and binding.get('goal')=='save' and row.get('id')==prepared_row.get('rowId'),f'{sid}: preparation binding changed')
            check(request.get('prompt')==row.get('prompt') and request.get('images')==row.get('images'),f'{sid}: prepared inputs differ from snapshot')
            check(all(request.get(k)==row['params'].get(k) for k in ('model','gptStyle','resolution','aspectRatio','quality','transparent')),
                  f'{sid}: prepared parameters differ from snapshot')
            check(isinstance(request.get('saveDir'),str) and path_key(request['saveDir'])==path_key(t['output_dir']),f'{sid}: prepared save destination differs')
        rb['source_snapshot_sha256']=sha(path)
        self.state['readbacks']=rb
        atomic_json(self.folder/'readback.json',rb)
        self.save()

    def preflight(self,sids=None):
        for t in self.package['tasks']:
            if sids is not None and t['id'] not in sids:continue
            wid=self.state['id_map'][t['workshop_ref']]
            result=self.call('run_preflight',{'projectId':self.state['project_id'],'nodeId':wid,'goal':'save'})
            check(result.get('blocked') is False and not any(i.get('severity')=='error' for i in result.get('issues',[])),
                  f"{t['id']}: preflight blocked or incomplete")
        self.verify_snapshot()

    def prepare(self,package_path):
        check(self.state is None,'Run already exists; do not recreate or overwrite it')
        check(not any(p.name!='executor.lock' for p in self.folder.iterdir()),'Use a new empty run directory')
        p=read(package_path);verify_package(p)
        check(p['ready_stage']!='repair' or p.get('repair_canvas_version')==1,
              'New repair preparation requires original-canvas binding; old runs remain readable/collectible')
        check(all(not Path(t['output_dir']).exists() for t in p['tasks']),
              'An attempt output directory already exists; compile a new attempt instead of reusing it')
        self.package=p
        atomic_json(self.folder/'package.json',p)
        self.state={'version':1,'run_id':uuid.uuid4().hex,'status':'preparing','project_id':None,'revision':0,
                    'package_sha256':sha(self.folder/'package.json'),'created_at_ms':round(self.clock()*1000),
                    'source_package_sha256':sha(package_path),
                    'id_map':{},'readbacks':{},'batches':[],'tasks':{},'submission_authorized':False}
        self.save()
        try:
            self.bootstrap()
            for model in sorted({t['model_id'] for t in p['tasks']}):
                cap=self.call('model_get_capabilities',{'modelId':model})
                check(cap.get('accountAvailable') is True,f'Required model unavailable: {model}')
            existing_ids=set();operations=p['operations']
            if p.get('repair_canvas_version')==1:
                from repair_canvas import context,placed_operations
                binding=context(p);source=read(Path(binding['source_run'])/'state.json')
                self.state.update(project_id=binding['project_id'],project_name=source.get('project_name',binding['project_id']))
                self.save()
                snapshot,_=self.snapshot('original-canvas-before-repair')
                operations,existing_ids=placed_operations(p,snapshot,self.state['run_id'])
                atomic_json(self.folder/'repair-operations.json',operations)
            else:
                self.state['project_name']=project_name(p,self.state['run_id']);self.save()
                data=self.call('project_create',{'kind':'batch','name':self.state['project_name']})
                check(isinstance(data.get('projectId'),str),'Project creation did not return projectId')
                self.state['project_id']=data['projectId'];self.save()
            summary=self.call('canvas_get_summary',{'projectId':self.state['project_id']})
            check(isinstance(summary.get('revision'),int) and not isinstance(summary['revision'],bool),'New project revision unavailable')
            self.state['revision']=summary['revision'];self.save()
            created=self.checked_mutation('workflow_apply_patch',{'operations':operations},'create-nodes')
            ids=created.get('idMap')
            expected={t[key] for t in p['tasks'] for key in ('load_ref','gen_ref','workshop_ref')}
            expected.update(t['note_ref'] for t in p['tasks'] if t.get('note_ref'))
            check(isinstance(ids,dict) and expected<=set(ids) and len({ids[k] for k in expected})==len(expected),
                  'Creation did not return unique per-page node mappings')
            check(not existing_ids.intersection(ids[k] for k in expected),'Repair mapping reused original nodes')
            self.state['id_map']={k:ids[k] for k in expected};self.save()
            self.state['node_notes']={ids[op['clientRef']]:op['data']['content'] for op in operations
                                      if op['op']=='createNode' and op.get('type')=='text/note'}
            self.save()
            for t in p['tasks']:
                self.checked_mutation('canvas_attach_local_images',{'nodeId':ids[t['load_ref']],'kind':'image',
                    'paths':[r['path'] for r in t['references']],'replace':True})
                self.checked_mutation('canvas_attach_local_images',{'nodeId':ids[t['workshop_ref']],'kind':'save',
                    'folderPath':t['output_dir']})
            ops=[{'op':'updateNode','nodeId':ids[t['gen_ref']],
                  'data':{'gptStyle':t['gpt_style'],'transparent':t['transparent']}} for t in p['tasks']]
            self.checked_mutation('workflow_apply_patch',{'operations':ops},'stage-options')
            prepared=self.call('canvas_prepare_run',{'projectId':self.state['project_id'],
                'nodeIds':[ids[t['workshop_ref']] for t in p['tasks']],'goal':'save'})
            atomic_json(self.folder/'prepare-response.json',prepared)
            check(prepared.get('generationSubmitted') is False,'Preparation did not confirm no generation submission')
            items=prepared.get('items',[])
            check(isinstance(items,list) and len(items)==len(p['tasks']) and all(isinstance(i,dict) for i in items),'Invalid preparation response')
            by_node={i.get('nodeId'):i for i in items}
            check(len(by_node)==len(items),'Duplicate preparation mapping')
            self.state['preparations']={}
            for t in p['tasks']:
                item=by_node.get(ids[t['workshop_ref']],{})
                check(item.get('ready') is True and item.get('preparationId') and item.get('requestDigest')
                      and len(item.get('rows',[]))==1 and item['rows'][0].get('ready') is True,
                      f"{t['id']}: preparation rejected or incomplete")
                self.state['preparations'][t['id']]=item
            self.save()
            snapshot,_=self.snapshot('before-pin')
            nodes={n['id']:(dict(n,**n['data']) if isinstance(n.get('data'),dict) else n) for n in snapshot['canvas']['nodes']}
            for t in p['tasks']:
                node=nodes[ids[t['workshop_ref']]];rows=node.get('rows',[])
                check(isinstance(rows,list) and len(rows)==1 and isinstance(rows[0],dict),
                      f"{t['id']}: execution row not materialized. MCP needs an unpaid prepare operation; no generation submitted")
                # Current MCP rejects round-tripping row.id/images. Do not send a
                # full row update or assume that a partial array update preserves it.
                # Native materialization must produce the approved settings, verified below.
            self.preflight()
            for t in p['tasks']:
                self.state['tasks'][t['id']]={'node_id':ids[t['workshop_ref']],'status':'ready','task_id':None}
            self.state['status']='prepared';self.save();self.event('prepared',count=len(p['tasks']))
            if p.get('repair_canvas_version')==1:
                from repair_canvas import trace
                atomic_json(self.folder/'canvas-trace.json',trace(p,self.state))
        except Exception as exc:
            self.state['status']='preparation_failed'
            self.state['error_type']=type(exc).__name__
            self.state['error']=str(exc) if isinstance(exc,ValueError) else 'MCP preparation failed; no generation submitted'
            self.save();self.write_report();raise
        return self.summary()

    def verify_frozen(self):
        check(sha(self.folder/'package.json')==self.state['package_sha256'],'Run package changed')
        verify_package(self.package)

    def list_tasks(self):
        items=[];cursor=None;seen=set()
        for _ in range(20):
            data=self.call('task_list',dict({'projectId':self.state['project_id'],'limit':100},**({'cursor':cursor} if cursor else {})))
            check(isinstance(data.get('items'),list),'Invalid task listing')
            items.extend(data['items']);cursor=data.get('nextCursor')
            if not cursor:return items
            check(cursor not in seen,'Repeated task-list cursor');seen.add(cursor)
        raise ValueError('Task listing exceeded pagination bound; no guessed mapping')

    def bind(self,sid,task_id):
        check(isinstance(task_id,str) and task_id,'Missing task ID')
        check(not any(k!=sid and v.get('task_id')==task_id for k,v in self.state['tasks'].items()),'One remote task cannot represent two pages')
        task=self.state['tasks'][sid]
        check(task.get('task_id') in (None,task_id),'Task mapping cannot change')
        task.update(task_id=task_id,status='queued')

    def submit(self,sids):
        check(self.state.get('submission_authorized') is True,'Submission not authorized')
        check(sids and len(sids)==len(set(sids)) and all(sid in self.state['tasks'] and self.state['tasks'][sid]['status']=='ready' for sid in sids),
              'Only never-submitted ready pages can be submitted')
        if self.package['ready_stage']=='repair' or 'repair_authorization' in self.package:
            check(self.package.get('repair_authorization_version')==1,
                  'Historical repair can be read/collected, but new generation requires a newly authorized repair package')
            grant=self.package['repair_authorization']
            spent=sum(len(b['local_ids']) for b in self.state['batches'])
            check(spent+len(sids)<=grant['max_generations'],'Repair generation count exceeds the recorded batch allowance')
        self.verify_frozen();self.preflight(sids)
        for t in self.package['tasks']:
            if t['id'] in sids:
                check(not Path(t['output_dir']).exists() or not any(Path(t['output_dir']).iterdir()),
                      f"{t['id']}: output directory is not empty before initial submission")
        before=[t['id'] for t in self.list_tasks() if isinstance(t.get('id'),str)]
        batch={'id':uuid.uuid4().hex,'local_ids':list(sids),'node_ids':[self.state['tasks'][sid]['node_id'] for sid in sids],
               'preparation_ids':{sid:self.state['preparations'][sid]['preparationId'] for sid in sids},
               'before_task_ids':before,'intent_at_ms':round(self.clock()*1000),'status':'intent_saved'}
        self.state['batches'].append(batch)
        self.state['status']='running'
        for sid in sids:self.state['tasks'][sid].update(status='submission_unknown',submitted_at_ms=batch['intent_at_ms'])
        self.save()  # Persist before the non-idempotent, potentially paid request.
        self.event('submit_intent',local_ids=sids,node_count=len(sids))
        try:
            args={'projectId':self.state['project_id'],'nodeIds':batch['node_ids'],'goal':'save'}
            # 1.8.8 checks each workshop's current preparation for nodeIds.
            # Its optional singular preparationId is only valid for a single target.
            if len(sids)==1:args['preparationId']=batch['preparation_ids'][sids[0]]
            data=self.call('canvas_run_node',args)
            atomic_json(self.folder/('submit-'+batch['id']+'.json'),data)
            runs=data.get('runs')
            if runs is None and data.get('nodeId'):runs=[data]
            check(isinstance(runs,list),'No authoritative per-workshop submission mapping returned')
            by_node={};valid=True
            for row in runs:
                if not isinstance(row,dict) or row.get('nodeId') not in batch['node_ids'] or row['nodeId'] in by_node:
                    valid=False;break
                by_node[row['nodeId']]=row
            check(valid,'Unexpected or duplicate workshop acknowledgement')
            for sid in sids:
                local=self.state['tasks'][sid];row=by_node.get(local['node_id'],{})
                if row.get('taskId') and row['taskId'] not in before:self.bind(sid,row['taskId'])
                elif row.get('status') in ('blocked','rejected') and not row.get('taskId'):
                    local.update(status='submission_rejected',error='Server explicitly did not start this workshop')
            batch['status']='acknowledged'
        except (TransportError,ToolError,ValueError) as exc:
            batch['status']='unknown';batch['error_type']=type(exc).__name__
            # Never reissue canvas_run_node for these IDs, including after restart.
        self.save()

    def recover_unknown(self):
        unknown=[sid for sid,t in self.state['tasks'].items() if t['status']=='submission_unknown']
        if not unknown:return
        remote=self.list_tasks()
        for sid in unknown:
            local=self.state['tasks'][sid]
            batch=next(b for b in self.state['batches'] if sid in b['local_ids'])
            matches=[r for r in remote if r.get('projectId')==self.state['project_id']
                     and r.get('runTargetId')==local['node_id'] and r.get('runMode')=='target'
                     and r.get('id') not in batch['before_task_ids']
                     and isinstance(r.get('startedAt'),(int,float))
                     and r['startedAt']>=batch['intent_at_ms']-2000]
            if len(matches)==1:self.bind(sid,matches[0]['id']);self.event('submission_recovered',local_id=sid)
            elif len(matches)>1:local['error']='Ambiguous tasks for this workshop; no automatic selection'
        self.save()

    def collect_one(self,sid,remote):
        local=self.state['tasks'][sid]
        if not remote.get('outputs',{}).get('generated'):
            local['status']='awaiting_output';return
        package=copy.deepcopy(self.package);package['tasks']=[t for t in package['tasks'] if t['id']==sid]
        state={'id_map':self.state['id_map'],'readbacks':self.state['readbacks'],
               'runs':[{'nodeId':local['node_id'],'taskId':local['task_id']}],'before_paths':{sid:[]},
               'selected_candidates':self.state.get('selected_candidates',{})}
        dest=self.folder/'returns'/(sid+'-'+uuid.uuid4().hex)
        try:
            result=reconcile(package,state,{local['task_id']:remote},dest)
            local.update(status='selection_required' if result['selection_required'] else 'verified',
                         return_path=str(dest/'agent-return.json'),ended_at_ms=remote.get('endedAt'))
            local.pop('error',None)
        except OSError as exc:
            local.update(status='collection_pending',error=str(exc),ended_at_ms=remote.get('endedAt'))
        except (ValueError,KeyError,TypeError) as exc:
            local.update(status='output_invalid',error=str(exc),ended_at_ms=remote.get('endedAt'))
        self.event('page_terminal',local_id=sid,status=local['status'])

    def recollect(self):
        """One local retry per failed collection, using recorded tasks; no MCP calls."""
        self.verify_frozen()
        for sid,local in self.state['tasks'].items():
            if local['status'] not in ('collection_pending','output_invalid'):continue
            remote=read(self.folder/'tasks'/(sid+'.json'))
            check(remote.get('id')==local.get('task_id') and remote.get('projectId')==self.state['project_id']
                  and remote.get('runTargetId')==local['node_id'] and remote.get('runMode')=='target'
                  and remote.get('status')=='done','Recorded collection task identity changed')
            self.collect_one(sid,remote)
        if self.state.get('postflight_verified'):
            self.state['status']=self.terminal_status() or self.state['status']
        self.save();self.write_report()
        return self.summary()

    def poll(self):
        self.recover_unknown()
        for sid,local in self.state['tasks'].items():
            if not local.get('task_id') or local['status'] in FINAL:continue
            remote=self.call('task_get',{'projectId':self.state['project_id'],'taskId':local['task_id']})
            check(remote.get('id')==local['task_id'] and remote.get('projectId')==self.state['project_id']
                  and remote.get('runTargetId')==local['node_id'] and remote.get('runMode')=='target',
                  f'{sid}: remote task/workshop binding mismatch')
            atomic_json(self.folder/'tasks'/(sid+'.json'),remote)
            local['remote_status']=remote.get('status')
            local['started_at_ms']=remote.get('startedAt')
            if remote.get('status') in ('error','failed','stopped','cancelled'):
                local.update(status='failed',error='Remote task ended unsuccessfully',ended_at_ms=remote.get('endedAt'))
            elif remote.get('status')=='done':
                self.collect_one(sid,remote)
            elif remote.get('status') in ('queued','pending','running'):
                local['status']='queued' if remote['status'] in ('queued','pending') else 'running'
            else:
                raise ValueError(f'{sid}: unrecognized remote status; no retry authorized')
            self.save()

    def summary(self):
        counts={}
        for task in self.state.get('tasks',{}).values():counts[task['status']]=counts.get(task['status'],0)+1
        return {'status':self.state['status'],'project_id':self.state.get('project_id'),'project_name':self.state.get('project_name'),'pages':len(self.state.get('tasks',{})),
                'counts':counts,'visual_status':'needs_agent_review','state_path':str(self.state_path)}

    def terminal_status(self):
        states=[t['status'] for t in self.state['tasks'].values()]
        if not states or not all(s in FINAL for s in states):return None
        if any(s in ('failed','output_invalid','submission_rejected') for s in states):return 'partial_failure'
        if 'collection_pending' in states:return 'collection_pending'
        return 'selection_required' if 'selection_required' in states else 'complete_needs_review'

    def finish(self):
        status=self.terminal_status()
        if status is None:return False
        self.verify_snapshot()  # No preflight on failed rows; inspect configuration without rerunning them.
        self.state['postflight_verified']=True
        self.state['status']=status
        self.save()
        self.write_report()
        return True

    def write_report(self):
        report=dict(self.summary(),tasks=self.state['tasks'],batches=self.state['batches'],
                    elapsed_ms=round(self.clock()*1000)-self.state['created_at_ms'],
                    auto_retries=0,submit_calls=len(self.state['batches']),
                    confirmed_task_count=sum(bool(t.get('task_id')) for t in self.state['tasks'].values()),
                    error=self.state.get('error'),
                    generation_authorized_by='explicit run --execute plus approved package authority')
        report['generation_tasks_submitted']=sum(len(b['local_ids']) for b in self.state['batches'])
        report['repair_authorization']=self.package.get('repair_authorization')
        report['canvas_trace_path']=str(self.folder/'canvas-trace.json') if self.package.get('repair_canvas_version')==1 else None
        from delivery_summary import summarize
        try:
            report['usage']=summarize([self.folder])
        except (ValueError,OSError,KeyError,TypeError) as exc:
            report['usage']={'status':'accounting_incomplete','actual_star_coins':None,
                             'star_coins_status':'pending_verification','error_type':type(exc).__name__}
        atomic_json(self.folder/'report.json',report)

    def select_candidates(self,selections):
        """Local-only selection from already verified candidates; never submit."""
        self.verify_frozen()
        check(isinstance(selections,dict) and selections,'Provide per-page path/hash/evidence selections')
        updates={}
        for sid,choice in selections.items():
            check(sid in self.state['tasks'] and self.state['tasks'][sid]['status']=='selection_required',
                  'Selection only applies to a page awaiting candidate choice')
            local=self.state['tasks'][sid]
            package=copy.deepcopy(self.package);package['tasks']=[t for t in package['tasks'] if t['id']==sid]
            state={'id_map':self.state['id_map'],'readbacks':self.state['readbacks'],
                   'runs':[{'nodeId':local['node_id'],'taskId':local['task_id']}],
                   'before_paths':{sid:[]},'selected_candidates':{sid:choice}}
            dest=self.folder/'returns'/(sid+'-selection-'+uuid.uuid4().hex)
            remote=read(self.folder/'tasks'/(sid+'.json'))
            result=reconcile(package,state,{local['task_id']:remote},dest)
            check(not result['selection_required'],'Candidate selection incomplete')
            updates[sid]=str(dest/'agent-return.json')
        for sid,path in updates.items():
            self.state['tasks'][sid].update(status='verified',return_path=path)
        self.state.setdefault('selected_candidates',{}).update(selections)
        if self.state.get('postflight_verified') and all(t['status']=='verified' for t in self.state['tasks'].values()):
            self.state['status']='complete_needs_review'
        self.save();self.write_report()
        return self.summary()

    def run(self,execute=False,max_wait=600,poll_interval=5,max_in_flight=None,resume=False):
        check(self.state and self.state['status'] not in ('preparing','preparation_failed'),'Prepare a complete run first')
        self.verify_frozen()
        self.bootstrap()
        check(math.isfinite(max_wait) and 0<=max_wait<=3600 and math.isfinite(poll_interval) and 0<poll_interval<=60,'Invalid bounded wait settings')
        check(max_in_flight is None or (isinstance(max_in_flight,int) and not isinstance(max_in_flight,bool) and max_in_flight>0),'Invalid concurrency limit')
        if resume:
            check(self.state.get('submission_authorized') is True,'This run was never authorized for submission')
            self.recollect()
        else:
            check(execute,'Submission requires explicit --execute and actual user authority')
            check(self.state['status']=='prepared','Run already started; use resume, never resubmit')
            self.state.update(submission_authorized=True,max_in_flight=max_in_flight or len(self.package['tasks']))
            check(isinstance(self.state['max_in_flight'],int) and self.state['max_in_flight']>0,'Invalid concurrency limit')
        self.state['status']='running';self.save()
        deadline=self.clock()+max_wait
        try:
            while True:
                active=sum(t['status'] in ACTIVE for t in self.state['tasks'].values())
                slots=self.state['max_in_flight']-active
                ready=[sid for sid,t in self.state['tasks'].items() if t['status']=='ready']
                if ready and slots>0:self.submit(ready[:slots])
                self.poll()
                if self.finish():break
                if self.clock()>=deadline:
                    self.state['status']='submission_unknown' if any(t['status']=='submission_unknown' for t in self.state['tasks'].values()) else 'timed_out'
                    self.save();break
                self.progress(self.summary());self.sleep(min(poll_interval,max(0,deadline-self.clock())))
        except (ToolError,TransportError,ValueError,OSError,KeyError) as exc:
            self.state['status']='blocked';self.state['error_type']=type(exc).__name__
            self.state['error']=str(exc) if not isinstance(exc,(ToolError,TransportError)) else 'MCP failure; inspect/resume known tasks, never resubmit'
            self.save()
        self.progress(self.summary())
        self.write_report()
        return self.summary()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--connection',type=Path,help='Local exported MCP JSON; never copy credentials into the skill/run package')
    p.add_argument('--server',default='synmew-canvas')
    p.add_argument('--rpc-timeout',type=float,default=45)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    prep=sub.add_parser('prepare');prep.add_argument('package',type=Path);prep.add_argument('run_dir',type=Path)
    run=sub.add_parser('run');run.add_argument('package',type=Path);run.add_argument('run_dir',type=Path)
    run.add_argument('--execute',action='store_true');run.add_argument('--max-in-flight',type=int)
    resume=sub.add_parser('resume');resume.add_argument('run_dir',type=Path)
    for parser in (run,resume):
        parser.add_argument('--max-wait',type=float,default=600);parser.add_argument('--poll-interval',type=float,default=5)
    status=sub.add_parser('status');status.add_argument('run_dir',type=Path)
    collect=sub.add_parser('collect');collect.add_argument('run_dir',type=Path);collect.add_argument('--selections',type=Path,required=True)
    recollect=sub.add_parser('recollect');recollect.add_argument('run_dir',type=Path)
    a=p.parse_args()
    try:
        check(math.isfinite(a.rpc_timeout) and 0<a.rpc_timeout<=60,'RPC timeout must be within 0..60 seconds')
        if a.command=='status':
            print(json.dumps(run_status(a.run_dir),ensure_ascii=False,indent=2));return 0
        if a.command=='recollect':
            with run_lock(a.run_dir):result=Executor(None,a.run_dir).recollect()
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result['status']=='complete_needs_review' else 3
        if a.command=='collect':
            with run_lock(a.run_dir):
                result=Executor(None,a.run_dir).select_candidates(read(a.selections))
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result['status']=='complete_needs_review' else 3
        check(a.connection is not None,'Provide --connection with local MCP stdio configuration')
        if a.command=='run':check(a.execute,'run requires --execute; preparation alone cannot spend')
        if a.command in ('prepare','run') and not a.run_dir.exists():a.run_dir.mkdir(parents=True)
        if a.command=='resume':check((a.run_dir/'state.json').is_file(),'Run state missing')
        with ready_client(load_connection(a.connection,a.server),rpc_timeout=a.rpc_timeout,factory=StdioMCP) as client:
            if a.command=='doctor':
                print(json.dumps(doctor(client),ensure_ascii=False,indent=2));return 0
            with run_lock(a.run_dir):
                worker=Executor(client,a.run_dir,progress=lambda value:print(json.dumps(value,ensure_ascii=False),flush=True))
                if worker.state is not None and a.command in ('prepare','run'):
                    check(sha(a.package)==worker.state.get('source_package_sha256'),'Supplied package differs from this prepared run')
                if worker.state is None:worker.prepare(a.package)
                if a.command=='prepare':
                    check(worker.state['status']=='prepared','Existing run is not prepared; inspect status')
                    print(json.dumps(worker.summary(),ensure_ascii=False));return 0
                from master_fallback import run_chain
                result=run_chain(worker,execute=getattr(a,'execute',False),max_wait=a.max_wait,poll_interval=a.poll_interval,
                                  max_in_flight=getattr(a,'max_in_flight',None),resume=a.command=='resume')
                return {'complete_needs_review':0,'selection_required':3,'timed_out':4,'submission_unknown':5}.get(result['status'],2)
    except (ValueError,OSError,KeyError,TypeError,ToolError,TransportError) as exc:
        p.exit(2,str(exc)+'\n')


if __name__=='__main__':raise SystemExit(main())
