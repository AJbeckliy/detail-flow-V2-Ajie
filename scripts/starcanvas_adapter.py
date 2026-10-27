"""Transport ready Agent prompts to Starcanvas unchanged; verify returned files."""
import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path


LOCKED_PROFILE = 'pt25-stable-sunburst-v4'
ENTERPRISE_PROFILE = 'pt25-stage-sunburst-v3'
LEGACY_PROFILE = 'pt25-1k-enterprise-v1'
LOCKED_QUALITY = 'auto'
PRODUCT_ONLY_WORKFLOWS = ('detail-flow-copy-led-v2', 'detail-flow-direct-v3', 'detail-flow-direct-v4')


def task_profile(task, profile=LOCKED_PROFILE):
    """Requested UI model and effective execution version, fixed per task kind."""
    check(profile in (LOCKED_PROFILE, ENTERPRISE_PROFILE, LEGACY_PROFILE), 'Unknown execution profile')
    check(task.get('kind') in ('master', 'slice'), 'Unknown task kind for fixed profile')
    if profile == LOCKED_PROFILE:
        check(task.get('master_fallback_tier',0) == 0, 'Stable profile has no enterprise fallback tiers')
        return {'model':'gpt-image-2.5-wd','resolution':'1K','quality':'auto',
                'gptStyle':'sunburst','transparent':False}
    if profile == LEGACY_PROFILE:
        return {'model':'gpt-image-2.5-1k-qy','resolution':'1K','quality':'auto',
                'gptStyle':'none','transparent':False}
    tier=task.get('master_fallback_tier',0)
    check(type(tier) is int and tier in (0,1,2),'Invalid master fallback tier')
    check(task['kind']=='master' or tier==0,'Fallback is only available for masters')
    if task['kind']=='master' and tier:
        return {'model':'gpt-image-2.5-1k-qy' if tier==1 else 'gpt-image-2.5-wd',
                'resolution':'1K','quality':'auto','gptStyle':'sunburst','transparent':False}
    return {'model':'gpt-image-2.5-qy' if task['kind']=='master' else 'gpt-image-2.5-1k-qy',
            'resolution':'2K' if task['kind']=='master' else '1K',
            'quality':'auto','gptStyle':'sunburst','transparent':False}


def effective_model_ids(settings):
    """Accept only the requested family and matching sunburst/resolution aliases."""
    model=settings['model']
    values={model}
    if settings['gptStyle']=='sunburst' and model.endswith('-qy'):
        stem=model[:-3]  # enterprise models end in -qy
        values.add(stem+'-sunburst-qy')
        if model=='gpt-image-2.5-qy':
            values.add(stem+'-'+settings['resolution'].lower()+'-sunburst-qy')
    return values


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def resolve_manifest(manifest, base_dir):
    """Resolve input paths once, relative to the manifest, without mutating it."""
    result = copy.deepcopy(manifest)
    base = Path(base_dir).resolve()
    def absolute(value):
        p = Path(value)
        return str((base / p).resolve() if not p.is_absolute() else p.resolve())
    for task in result.get('tasks', []):
        task['prompt_path'] = absolute(task['prompt_path'])
        for ref in task.get('references', []):
            ref['path'] = absolute(ref['path'])
            if ref.get('source_path'):ref['source_path']=absolute(ref['source_path'])
    for anchor in result.get('frozen_planning', []): anchor['path'] = absolute(anchor['path'])
    if isinstance(result.get('visual_master'), dict) and result['visual_master'].get('path'):
        result['visual_master']['path'] = absolute(result['visual_master']['path'])
    if isinstance(result.get('review_delivery'), dict) and result['review_delivery'].get('receipt_path'):
        result['review_delivery']['receipt_path'] = absolute(result['review_delivery']['receipt_path'])
    if isinstance(result.get('approved_plan'),dict) and result['approved_plan'].get('path'):
        result['approved_plan']['path']=absolute(result['approved_plan']['path'])
    if isinstance(result.get('repair_context'),dict) and result['repair_context'].get('source_run'):
        result['repair_context']['source_run']=absolute(result['repair_context']['source_run'])
    if result.get('workflow') in PRODUCT_ONLY_WORKFLOWS and result.get('execution_profile',LOCKED_PROFILE)==LOCKED_PROFILE:
        result['ratio_policy']='confirmed-ratio-v1'
        binding=result.get('approved_plan',{})
        plan=read(binding['path']) if binding.get('path') and Path(binding['path']).is_file() else {}
        pages={p.get('slice_id'):p for p in plan.get('pages',[]) if isinstance(p,dict)}
        for task in result.get('tasks',[]):
            if 'aspect_ratio' not in task:
                page=pages.get(task.get('page_id',task['id'].removeprefix('screen-')),{})
                task['aspect_ratio']=page.get('aspect_ratio',plan.get('aspect_ratio','9:16'))
    return result


def path_key(path):
    return os.path.normcase(str(Path(path).resolve()))


def evidence(value):
    return isinstance(value, str) and bool(value.strip())


def stage_authority(manifest, gate, fallback):
    policy = manifest.get('stage_policy', {})
    check(isinstance(policy, dict) and set(policy) <= {'design', 'master'}, 'Invalid stage_policy')
    for value in policy.values():
        check(isinstance(value, dict) and set(value) == {'mode', 'evidence'}
              and value.get('mode') in ('approved', 'delegated', 'waived')
              and evidence(value.get('evidence')), 'Stage policy needs a mode and actual authority evidence')
    entry = policy.get(gate)
    if entry is not None: return entry['mode']
    check(evidence(fallback), gate + ' approval evidence required')
    return 'approved'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(value, message):
    if not value: raise ValueError(message)


def validate_review_delivery(manifest):
    """Verify an editable artifact was delivered, not that a human approved it."""
    delivery=manifest.get('review_delivery')
    check(isinstance(delivery,dict), 'Editable HTML review delivery required; a static PNG is not the review editor')
    if delivery.get('kind') == 'user_alternative':
        check(evidence(delivery.get('evidence')), 'Alternative review format needs explicit user authority')
        return
    check(delivery.get('kind') == 'editable_html', 'Unsupported review delivery kind')
    path=delivery.get('receipt_path')
    check(isinstance(path,str) and Path(path).is_file(), 'Review receipt missing; run prepare_review.py')
    check(sha(path) == delivery.get('receipt_sha256'), 'Review receipt changed')
    check(evidence(delivery.get('presentation_evidence')), 'Record the actual opened HTML or user-visible review link')
    receipt=read(path)
    check(receipt.get('artifact_kind')=='editable_html_review', 'Review receipt is not an editable HTML artifact')
    for field,digest in (('html_path','html_sha256'),('source_plan','source_plan_sha256')):
        value=receipt.get(field)
        check(isinstance(value,str) and Path(value).is_file() and sha(value)==receipt.get(digest), 'Review artifact/source changed or missing')
    html=Path(receipt['html_path']).read_text(encoding='utf-8')
    check('<script id="data" type="application/json">' in html and 'id="export"' in html and 'textarea' in html and '/*__PAYLOAD__*/' not in html,
          'Review file lacks the editable payload or export controls')


def validate_master_contract(manifest):
    """Check current-workflow evidence bindings, not the truth of human approval."""
    workflow = manifest.get('workflow')
    if workflow is None:
        return  # Historical v1 manifests retain their original contract.
    check(workflow in ('detail-flow-master-v1', *PRODUCT_ONLY_WORKFLOWS), 'Unknown workflow contract')
    stage_authority(manifest, 'design', manifest.get('design_approval'))
    tasks = manifest.get('tasks', [])
    check(tasks, 'No ready tasks')
    kinds = {t.get('kind') for t in tasks}
    stage = manifest.get('ready_stage')
    check(stage in ('master', 'production', 'sample', 'remaining', 'repair'), 'Invalid master workflow stage')
    check(kinds in ({'master'}, {'slice'}), 'Do not mix master and dependent pages in one batch')
    for t in tasks:
        refs = t.get('references', [])
        check(refs and refs[0].get('role') == 'product', 'First reference must be product authority')
    if kinds == {'master'}:
        if workflow in ('detail-flow-direct-v3','detail-flow-direct-v4'):
            request=manifest.get('master_request')
            check(isinstance(request,dict) and evidence(request.get('evidence')),
                  'Optional visual preview requires explicit user master_request.evidence')
        check(stage in ('master', 'repair'), 'Master task at wrong stage')
        check(len(tasks) == 1, 'One visual master per batch')
        if workflow not in PRODUCT_ONLY_WORKFLOWS or manifest.get('execution_profile',LOCKED_PROFILE)!=LOCKED_PROFILE:
            ratio=('9:16' if tasks[0].get('master_fallback_tier',0)==2 else '9:21') if workflow in PRODUCT_ONLY_WORKFLOWS else '1:3'
            check(tasks[0].get('aspect_ratio') == ratio, 'Visual master must use '+ratio)
        return
    check(stage in ('production', 'sample', 'remaining', 'repair'), 'Final pages cannot run at master stage')
    if stage == 'sample':
        check(len(tasks) <= 2, 'Review the first up to 2 pages before remaining pages')
    if stage == 'remaining':
        check(evidence(manifest.get('sample_review')), 'First-page vertical review evidence required')
    master = manifest.get('visual_master')
    if (workflow in ('detail-flow-direct-v3','detail-flow-direct-v4') and master is None
            and 'master' not in manifest.get('stage_policy',{}) and 'master_request' not in manifest):
        for t in tasks:
            check(workflow=='detail-flow-direct-v4' or all(r.get('role') == 'product' for r in t['references']), 'Final pages accept product references only')
        return
    mode = stage_authority(manifest, 'master', master.get('approval_evidence') if isinstance(master, dict) else None)
    if mode == 'waived' and master is None:
        check(workflow in PRODUCT_ONLY_WORKFLOWS, 'Master waiver requires the product-only workflow')
        for t in tasks:
            check(workflow=='detail-flow-direct-v4' or all(r.get('role') == 'product' for r in t['references']), 'Final pages accept product references only')
        return
    check(isinstance(master, dict), 'Confirmed visual master binding required')
    path, digest = master.get('path'), master.get('sha256')
    check(isinstance(path, str) and Path(path).is_file(), 'Confirmed master file missing')
    check(isinstance(digest, str) and re.fullmatch(r'[a-fA-F0-9]{64}', digest), 'Master SHA256 required')
    check(sha(path) == digest.lower(), 'Confirmed master changed; review and rebind the version')
    canonical = path_key(path)
    if workflow in PRODUCT_ONLY_WORKFLOWS:
        # Approval metadata is retained; it is not an instruction to attach the master.
        for t in tasks:
            check(workflow=='detail-flow-direct-v4' or all(r.get('role') == 'product' for r in t['references']),
                  'Copy-led final pages accept product references only; no master, style or sketch')
            for ref in t['references']:
                check(path_key(ref['path']) != canonical
                      and sha(ref['path']) != digest.lower(),
                      'Confirmed master cannot be disguised as a product reference')
        return
    for t in tasks:
        refs = [r for r in t['references'] if r.get('role') == 'visual_master']
        check(len(refs) == 1, 'Each final page requires exactly one visual_master reference')
        check(path_key(refs[0]['path']) == canonical,
              'Page references a different master version')
        check(sha(refs[0]['path']) == digest.lower(), 'Page master hash mismatch')


def copy_leaves(value,prefix=''):
    """Visible copy only, keeping the source keys for representative master modules."""
    if isinstance(value,dict):
        return [leaf for key,item in value.items() for leaf in copy_leaves(item,(prefix+'.' if prefix else '')+str(key))]
    if isinstance(value,list):
        return [leaf for key,item in enumerate(value) for leaf in copy_leaves(item,(prefix+'.' if prefix else '')+str(key))]
    return [(prefix,str(value))] if isinstance(value,(str,int,float)) and not isinstance(value,bool) and str(value).strip() else []


def validate_review_binding(manifest):
    binding=manifest.get('approved_plan')
    check(isinstance(binding,dict) and evidence(binding.get('approval_evidence')),
          'Current approved_plan path, sha256 and approval_evidence required')
    path=binding.get('path');digest=binding.get('sha256')
    check(isinstance(path,str) and Path(path).is_file() and sha(path)==digest,'Approved plan revision changed or missing')
    plan=read(path);pages=plan.get('pages')
    check(isinstance(pages,list) and pages and all(isinstance(p,dict) and evidence(p.get('slice_id')) for p in pages),
          'Approved plan needs pages with stable string slice_id values')
    ids=[p['slice_id'] for p in pages]
    check(len(set(ids))==len(ids),'Approved plan page IDs must be unique')
    by_id={p['slice_id']:p for p in pages};selected=[]
    delivery=manifest.get('review_delivery',{})
    if delivery.get('kind')=='editable_html':
        receipt=read(delivery['receipt_path'])
        check(digest==receipt['source_plan_sha256'] or plan.get('review_state',{}).get('source_plan_sha256')==receipt['source_plan_sha256'],
              'Approved plan does not belong to the delivered review revision')
    for task in manifest['tasks']:
        if task['kind']=='slice':
            page_ids=[task.get('page_id',task['id'].removeprefix('screen-'))]
            check(not task.get('copy_keys'),'Final page must preserve all approved copy')
            selected.extend(page_ids)
        else:
            page_ids=task.get('page_ids',ids if len(ids)==1 else None)
            check(isinstance(page_ids,list) and page_ids,'Master needs representative approved page_ids')
        check(len(set(page_ids))==len(page_ids) and all(pid in by_id for pid in page_ids),'Task references unknown or duplicate approved page IDs')
        prompt=Path(task['prompt_path']).read_bytes().decode('utf-8').replace('\r\n','\n')
        choices=task.get('copy_keys',{})
        check(isinstance(choices,dict) and set(choices)<=set(page_ids),'Invalid representative master copy keys')
        for pid in page_ids:
            if task['kind']=='slice' and manifest.get('ratio_policy')=='confirmed-ratio-v1':
                approved_ratio=by_id[pid].get('aspect_ratio',plan.get('aspect_ratio'))
                if approved_ratio is not None:
                    check(task['aspect_ratio']==approved_ratio,f'{task["id"]}: ratio differs from approved page {pid}')
            leaves=dict(copy_leaves(by_id[pid].get('text_exact',{})))
            keys=choices.get(pid,list(leaves))
            check(isinstance(keys,list) and (bool(keys) or not leaves) and all(key in leaves for key in keys),
                  'Master copy keys are not from approved text_exact')
            for key in keys:
                check(leaves[key].replace('\r\n','\n') in prompt,f'{task["id"]}: approved copy missing or stale at {pid}.{key}')
    if selected:
        check(len(set(selected))==len(selected),'Multiple tasks map to the same approved page')
        if manifest['ready_stage']=='production':
            check(set(selected)==set(ids),'Production page coverage differs from the approved plan; use an explicitly scoped repair/trial for a subset')


def validate_repair_authorization(manifest):
    """Check recorded repair scope/allowance, not the truth of human permission."""
    grant=manifest.get('repair_authorization')
    check(isinstance(grant,dict),'Additional repair generations require repair_authorization; initial production approval is not a repair allowance')
    check(grant.get('mode') in ('explicit','prior_allowance') and evidence(grant.get('evidence')),
          'Repair authorization needs its actual user evidence and mode')
    ids=grant.get('task_ids');actual=[t['id'] for t in manifest['tasks']]
    check(isinstance(ids,list) and all(isinstance(x,str) for x in ids) and len(ids)==len(set(ids))
          and set(ids)==set(actual),'Repair authorization page scope differs from this batch')
    limit=grant.get('max_generations')
    check(type(limit) is int and limit>=len(actual),'Repair max_generations must cover this batch; zero, missing or boolean limits are invalid')
    if grant['mode']=='prior_allowance':
        total=grant.get('allowance_total');used=grant.get('used_generations')
        check(type(total) is int and type(used) is int and 0<=used<=total and limit<=total-used,
              'Repair request exceeds remaining recorded allowance')
    return grant


def validate(manifest, *, require_review_binding=True, require_repair_authorization=True, require_repair_canvas=True):
    check(manifest.get('version')==1,'Unsupported transport manifest')
    check(manifest.get('ready_stage') in ('master','production','sample','remaining','repair'),'Missing approved ready stage')
    check(evidence(manifest.get('authority')),'Missing ready-stage authority; package does not authorize payment')
    if manifest.get('workflow') in (None, 'detail-flow-master-v1'):
        legacy = manifest.get('legacy_experiment')
        check(isinstance(legacy, dict) and evidence(legacy.get('evidence')),
              'New legacy compilation requires explicit legacy_experiment.evidence; use detail-flow-direct-v3 normally')
    if manifest.get('workflow') in PRODUCT_ONLY_WORKFLOWS:
        validate_review_delivery(manifest)
        if manifest['ready_stage'] in ('sample','remaining'):
            check(evidence(manifest.get('staged_review_authority')),
                  'Use production for the whole approved set; staged sample/remaining needs explicit user authority')
    tasks=manifest.get('tasks',[]);check(tasks,'No ready tasks')
    if ('repair_authorization_version' in manifest or 'repair_authorization' in manifest
            or (require_repair_authorization and manifest['ready_stage']=='repair')):
        check(manifest.get('repair_authorization_version',1)==1,'Unknown repair authorization version')
        validate_repair_authorization(manifest)
    if 'repair_context' in manifest or 'repair_canvas_version' in manifest or (require_repair_canvas and manifest['ready_stage']=='repair'):
        from repair_canvas import context
        context(manifest)
    validate_master_contract(manifest)
    ids=[t['id'] for t in tasks]
    check(len(ids)==len(set(ids)),'Duplicate IDs')
    for t in tasks:
        check(re.fullmatch(r'[a-z0-9][a-z0-9_-]*',t['id']),'Unsafe task ID')
        check(t.get('kind') in ('master','slice'),'Only detail-page generation is supported')
        check(Path(t['prompt_path']).is_file(),'Missing ready prompt')
        raw=Path(t['prompt_path']).read_bytes()
        prompt=raw.decode('utf-8');check(prompt.strip(),'Empty prompt')
        if t.get('prompt_sha256'):check(sha(t['prompt_path'])==t['prompt_sha256'].lower(),'Ready prompt changed')
        check(t.get('model_id') and t.get('resolution'),'Missing selected model/settings')
        if manifest.get('workflow') in PRODUCT_ONLY_WORKFLOWS:
            settings=task_profile(t,manifest.get('execution_profile',LOCKED_PROFILE))
            check(t['model_id'] == settings['model'] and t['resolution'] == settings['resolution']
                  and t.get('quality', LOCKED_QUALITY) == LOCKED_QUALITY
                  and t.get('gpt_style','sunburst')=='sunburst'
                  and t.get('transparent',False) is False,
                  f"Fixed production profile for {t['kind']} requires {settings['model']}, {settings['resolution']}, sunburst, quality=auto, transparent=false")
            if t['kind']=='slice' and manifest.get('execution_profile',LOCKED_PROFILE)!=LOCKED_PROFILE:
                check(t.get('aspect_ratio') == '9:16', 'Final page ratio must be 9:16')
        check(re.fullmatch(r'[1-9][0-9]*:[1-9][0-9]*',t.get('aspect_ratio','')),'Invalid ratio')
        check(t.get('references'),'Missing ordered references')
        for ref in t['references']:
            check(Path(ref['path']).is_file(),'Missing reference: '+ref['path'])
            if ref.get('sha256'):check(sha(ref['path'])==ref['sha256'].lower(),'Reference changed')
        if manifest.get('workflow') in PRODUCT_ONLY_WORKFLOWS:
            paths=[path_key(r['path']) for r in t['references']]
            digests=[sha(r['path']) for r in t['references']]
            check(len(paths)==len(set(paths)) and len(digests)==len(set(digests)),
                  'Duplicate input references; do not append or repeat product/style images')
        for dependency in t.get('wait_for',[]):
            check(dependency not in ids,'Dependent task is not ready for the same concurrent batch')
            check(dependency in manifest.get('completed_dependencies',[]),'Unresolved dependency')
    for anchor in manifest.get('frozen_planning',[]):
        check(Path(anchor['path']).is_file() and sha(anchor['path'])==anchor['sha256'].lower(),'Planning input changed')
    if manifest.get('workflow') in PRODUCT_ONLY_WORKFLOWS and (require_review_binding or 'review_binding_version' in manifest):
        check(manifest.get('review_binding_version',1)==1,'Unknown review binding version')
        validate_review_binding(manifest)
    if manifest.get('workflow')=='detail-flow-direct-v4':
        from reference_contract import validate_product,validate_references
        from planning_checks import validate_plan,DISPLAY_TEXT
        plan=read(manifest['approved_plan']['path'])
        validate_product(manifest,plan);validate_plan(plan);validate_references(manifest)
        pages={p['slice_id']:p for p in plan['pages']}
        for task in tasks:
            if task['kind']!='slice':continue
            page=pages[task.get('page_id',task['id'].removeprefix('screen-'))]
            prompt=Path(task['prompt_path']).read_text(encoding='utf-8').replace('\r\n','\n')
            check(page['visual_composition'].replace('\r\n','\n') in prompt,'Approved visual_composition missing from prompt')
            check(DISPLAY_TEXT[page['product_display']] in prompt,'Approved product-display instruction missing from prompt')
    return {'ready':True,'tasks':len(tasks),'prompt_transport':'unchanged'}


def transport_prompt(task):
    raw=Path(task['prompt_path']).read_bytes()
    if task.get('prompt_sha256'):check(hashlib.sha256(raw).hexdigest()==task['prompt_sha256'],'Prompt file changed after packaging')
    text=raw.decode('utf-8')
    policy=task.get('prompt_normalization')
    check(policy in (None,'trailing-crlf-v1'),'Unknown prompt normalization')
    if policy:text=text.rstrip('\r\n')
    if task.get('transport_prompt_sha256'):
        check(hashlib.sha256(text.encode('utf-8')).hexdigest()==task['transport_prompt_sha256'],'Transport prompt hash mismatch')
    return text


def compile_tasks(manifest, output, base_dir=None, *, reuse_preparation=False, require_review_binding=True):
    manifest = resolve_manifest(manifest, base_dir or Path.cwd())
    validate(manifest,require_review_binding=require_review_binding)
    dest=Path(output);check(not dest.exists() or reuse_preparation,'Preserve existing package')
    tasks=[];ops=[]
    for index,t in enumerate(manifest['tasks']):
        prompt=Path(t['prompt_path']).read_bytes().decode('utf-8')
        key=t['id'];load=key+'-load';gen=key+'-gen';workshop=key+'-workshop'
        inputs=[dict(ref,sha256=sha(ref['path']),**({'source_sha256':sha(ref['source_path'])} if ref.get('source_path') else {})) for ref in t['references']]
        task=dict(t,prompt_sha256=sha(t['prompt_path']),references=inputs,load_ref=load,gen_ref=gen,workshop_ref=workshop,output_dir=str((dest/key).resolve()))
        if manifest.get('workflow') in PRODUCT_ONLY_WORKFLOWS:
            task.update(gpt_style='sunburst',transparent=False,workshop_settings=dict(task_profile(t,manifest.get('execution_profile',LOCKED_PROFILE)),aspectRatio=t['aspect_ratio']))
            task['prompt_normalization']='trailing-crlf-v1'
            prompt=prompt.rstrip('\r\n')
            task['transport_prompt_sha256']=hashlib.sha256(prompt.encode('utf-8')).hexdigest()
        tasks.append(task)
        ops.extend([
            {'op':'createNode','clientRef':load,'type':'image/load-image-grid','x':0,'y':index*560},
            {'op':'createNode','clientRef':gen,'type':'ai-image/gpt-image','x':360,'y':index*560,'data':{'prompt':prompt,'modelType':t['model_id'],'resolution':t['resolution'],'aspectRatio':t['aspect_ratio'],'quality':t.get('quality','auto')}},
            {'op':'createNode','clientRef':workshop,'type':'image/workshop','x':720,'y':index*560},
            {'op':'connect','fromRef':load,'fromPort':'imageGroup','toRef':gen,'toPort':'image'},
            {'op':'connect','fromRef':gen,'fromPort':'image','toRef':workshop,'toPort':'image'}])
    package={'version':1,'ready_stage':manifest['ready_stage'],'authority':manifest['authority'],'tasks':tasks,'operations':ops,'frozen_planning':manifest.get('frozen_planning',[]),'paid_submission':False}
    if manifest['ready_stage']=='repair' or 'repair_context' in manifest:
        from repair_canvas import context
        package.update(repair_canvas_version=1,repair_context=context(manifest))
    for index,task in enumerate(tasks):
        sid=task['id'];page=task.get('page_id',sid.removeprefix('screen-'))
        note=('预览' if task['kind']=='master' else '首轮·第'+page+'屏')
        if 'repair_context' in package:
            binding=package['repair_context'];source=binding['source_nodes'][sid]
            note='返修R'+str(binding['round'])+'·第'+page+'屏\n问题：'+binding['issues'][sid]
            note+='\n原提示词节点：'+source['gen']+'\n原结果节点：'+source['workshop']
        task['canvas_note']=note+'\n本行从左到右：商品素材 → 完整提示词 → 生成结果。'
        task['note_ref']=sid+'-trace-note'
        ops.append({'op':'createNode','clientRef':task['note_ref'],'type':'text/note','x':-600,'y':index*560,
                    'data':{'content':task['canvas_note']}})
    if manifest['ready_stage']=='repair' or 'repair_authorization' in manifest:
        package.update(repair_authorization_version=1,repair_authorization=copy.deepcopy(manifest['repair_authorization']))
    if manifest.get('workflow') in PRODUCT_ONLY_WORKFLOWS:
        package['execution_profile'] = manifest.get('execution_profile',LOCKED_PROFILE)
        if require_review_binding or 'review_binding_version' in manifest:
            package.update(review_binding_version=1,approved_plan=manifest['approved_plan'])
        if all(t['kind']=='master' for t in tasks):
            stable=package['execution_profile']==LOCKED_PROFILE
            policy=manifest.get('master_fallback',{'enabled':not stable})
            check(isinstance(policy,dict) and type(policy.get('enabled')) is bool,'Invalid fallback policy')
            available=1 if stable else 3-tasks[0].get('master_fallback_tier',0)
            limit=policy.get('max_attempts',available if policy['enabled'] else 1)
            check(type(limit) is int and 1<=limit<=available,'Invalid max_attempts for selected profile; stable supports one attempt, never enterprise fallback')
            check(not stable or policy['enabled'] is False,'Stable preview has no automatic channel fallback; authorize a separate repair if needed')
            if not policy['enabled']:limit=1
            package['master_fallback']={'enabled':policy['enabled'],'max_attempts':limit,'trigger':'confirmed_terminal_service_failure'}
            if manifest.get('master_fallback_parent'):package['master_fallback_parent']=manifest['master_fallback_parent']
        package['reference_attachments']=[
            {'load_ref':task['load_ref'],'arguments':{'kind':'image','paths':[r['path'] for r in task['references']],'replace':True}}
            for task in tasks]
    for field in ('workflow', 'design_approval', 'visual_master', 'master_request', 'sample_review', 'staged_review_authority', 'stage_policy', 'legacy_experiment', 'completed_dependencies', 'review_delivery', 'ratio_policy', 'product_id', 'reference_policy'):
        if field in manifest: package[field] = manifest[field]
    if dest.exists():
        entries={p.name for p in dest.iterdir()}
        check(entries <= {'package.json'},'Existing preparation contains additional files; inspect without resubmission')
        if (dest/'package.json').exists():
            check(read(dest/'package.json')==package,'Existing fallback package differs from approved preparation')
            return {'package':str((dest/'package.json').resolve()),'tasks':len(tasks),'paid_submission':False}
    dest.mkdir(parents=True,exist_ok=reuse_preparation)
    (dest/'package.json').write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'package':str((dest/'package.json').resolve()),'tasks':len(tasks),'paid_submission':False}


def assert_effective_workshops(package, readbacks):
    """Check actual execution rows, not just upstream node settings."""
    if 'execution_profile' not in package: return  # Historical package inspection.
    check(package['execution_profile'] in (LOCKED_PROFILE, ENTERPRISE_PROFILE, LEGACY_PROFILE), 'Unknown execution profile')
    workshops=readbacks.get('workshops',{})
    issues=[]
    for task in package['tasks']:
        sid=task['id'];node=workshops.get(sid)
        settings=task_profile(task,package['execution_profile'])
        if (task['model_id']!=settings['model'] or task['resolution']!=settings['resolution']
                or task.get('quality','auto')!=settings['quality']
                or task.get('gpt_style',settings['gptStyle'])!=settings['gptStyle']
                or task.get('transparent',False) is not False):
            issues.append(f'{sid}: packaged task does not match locked profile')
        if package['execution_profile']==ENTERPRISE_PROFILE:
            ratio='9:21' if task['kind']=='master' and task.get('master_fallback_tier',0)!=2 else '9:16'
            if task['aspect_ratio']!=ratio:issues.append(f'{sid}: {task["kind"]} ratio must be {ratio}')
        if not isinstance(node,dict):
            issues.append(f'{sid}: missing actual workshop readback');continue
        rows=node.get('rows')
        if not isinstance(rows,list) or len(rows)!=1:
            issues.append(f'{sid}: expected exactly one execution row per task');continue
        row=rows[0]
        if not isinstance(row,dict):
            issues.append(f'{sid}: invalid workshop row');continue
        params=row.get('params',{})
        if not isinstance(params,dict): params={}
        expected=dict(settings,aspectRatio=task['aspect_ratio'])
        for key,value in expected.items():
            matched=(isinstance(params.get(key),str) and params[key] in effective_model_ids(settings)) if key=='model' else params.get(key)==value
            if not matched or (key=='transparent' and params.get(key) is not False):
                issues.append(f'{sid}: effective {key} must be {value!r}; got {params.get(key)!r}')
        if row.get('prompt') != transport_prompt(task):
            issues.append(f'{sid}: workshop prompt differs from approved prompt')
        images=row.get('images')
        expected_images=[path_key(r['path']) for r in task['references']]
        if not isinstance(images,list) or not all(isinstance(p,str) for p in images) or [path_key(p) for p in images]!=expected_images:
            issues.append(f'{sid}: workshop input images/order differ')
        prepared=node.get('runPreparation',{})
        native_prepared=isinstance(prepared,dict) and bool(prepared.get('id')) and bool(prepared.get('digest')) and prepared.get('goal')=='save'
        if node.get('autoSaveEnabled') is not True or (row.get('saveFilled') is not True and not ('saveFilled' not in row and native_prepared)):
            issues.append(f'{sid}: actual save configuration is not ready')
        save_dir=row.get('saveDir',node.get('autoSavePath') if native_prepared else None)
        if not isinstance(save_dir,str) or path_key(save_dir)!=path_key(task['output_dir']):
            issues.append(f'{sid}: workshop saveDir differs from this attempt output directory')
        if 'autoSavePath' in node and path_key(node['autoSavePath'])!=path_key(task['output_dir']):
            issues.append(f'{sid}: node save directory differs from this attempt')
    check(not issues,'Effective workshop readback failed:\n'+'\n'.join(issues))


def extract_readback(package, snapshot, id_map):
    """Normalize only observed node fields from one exported project snapshot."""
    raw_nodes=snapshot.get('canvas',{}).get('nodes')
    check(isinstance(raw_nodes,list),'Expected project snapshot canvas.nodes')
    nodes={}
    for node in raw_nodes:
        check(isinstance(node,dict) and isinstance(node.get('id'),str),'Invalid snapshot node')
        check(node['id'] not in nodes,'Duplicate snapshot node ID')
        payload=node.get('data')
        nodes[node['id']]=dict(node,**payload) if isinstance(payload,dict) else node
    result={'generators':{},'references':{},'workshops':{}}
    for task in package['tasks']:
        sid=task['id']
        selected=[]
        for key,typ in (('load_ref','image/load-image-grid'),('gen_ref','ai-image/gpt-image'),('workshop_ref','image/workshop')):
            node=nodes.get(id_map.get(task[key]))
            check(isinstance(node,dict) and node.get('type')==typ,f'{sid}: mapped {key} missing or wrong type')
            selected.append(node)
        loader,generator,workshop=selected
        images=loader.get('images')
        check(isinstance(images,list) and all(isinstance(i,dict) and isinstance(i.get('path'),str) for i in images),
              f'{sid}: loader image paths unavailable in actual snapshot')
        result['references'][sid]=[i['path'] for i in images]
        result['generators'][sid]={k:generator[k] for k in ('prompt','modelType','resolution','aspectRatio','quality') if k in generator}
        result['workshops'][sid]={k:workshop[k] for k in ('rows','autoSaveEnabled','autoSavePath','runPreparation') if k in workshop}
    assert_readback(package,result)
    return result


def readback_export(package_path, snapshot_path, id_map_path, output):
    dest=Path(output)
    check(not dest.exists(),'Preserve existing readback evidence')
    result=extract_readback(read(package_path),read(snapshot_path),read(id_map_path))
    result['source_snapshot_sha256']=sha(snapshot_path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'readback':'exact_match','tasks':len(result['generators']),'output':str(dest.resolve()),'paid_submission':False}


def assert_readback(package, readbacks):
    validate_master_contract(package)
    if 'review_delivery' in package: validate_review_delivery(package)
    if package.get('workflow')=='detail-flow-direct-v4':
        from reference_contract import validate_references
        binding=package['approved_plan']
        check(sha(binding['path'])==binding['sha256'],'Approved plan changed')
        validate_references(package)
    assert_effective_workshops(package,readbacks)
    generators=readbacks.get('generators',{})
    references=readbacks.get('references',{})
    for anchor in package.get('frozen_planning',[]):
        check(Path(anchor['path']).is_file() and sha(anchor['path'])==anchor['sha256'].lower(),'Frozen planning input changed after packaging')
    for t in package['tasks']:
        node=generators[t['id']]
        raw=Path(t['prompt_path']).read_bytes()
        check(hashlib.sha256(raw).hexdigest()==t['prompt_sha256'],'Prompt file changed after packaging')
        check(node.get('prompt')==transport_prompt(t),'Canvas modified prompt text')
        check(node.get('modelType')==t['model_id'] and node.get('resolution')==t['resolution'] and node.get('aspectRatio')==t['aspect_ratio'],'Canvas settings mismatch')
        check(node.get('quality') == t.get('quality', 'auto'), 'Canvas quality missing or mismatched; exact readback not established')
        expected=[path_key(ref['path']) for ref in t['references']]
        actual=[path_key(p) for p in references.get(t['id'],[])]
        check(actual==expected,'Canvas reference order/content list mismatch')
        for ref in t['references']:
            check(Path(ref['path']).is_file() and sha(ref['path'])==ref['sha256'],'Reference file changed after packaging')
    return {'readback':'exact_match','tasks':len(package['tasks'])}


def reconcile(package, state, snapshot, output):
    from PIL import Image
    dest=Path(output);check(not dest.exists(),'Preserve existing return package')
    assert_readback(package,state.get('readbacks',{}))
    map_=state['id_map'];runs=state['runs'];records=[];candidates=[];pending=[];echoes=[];rejected=[]
    for t in package['tasks']:
        workshop=map_[t['workshop_ref']]
        run=next((r for r in runs if r['nodeId']==workshop),None);check(run,'Missing remote task mapping')
        remote=snapshot[run['taskId']]
        check(remote.get('id')==run['taskId'] and remote.get('status')=='done','Task not completed')
        check(isinstance(remote.get('startedAt'),(int,float)) and isinstance(remote.get('endedAt'),(int,float)),'Task timing evidence required')
        previous={path_key(p) for p in state.get('before_paths',{}).get(t['id'],[])}
        unique={}
        outputs=remote.get('outputs',{})
        parent=outputs.get('nodeId')
        if parent is not None:check(parent==workshop,'Parent output belongs to another workshop')
        if remote.get('runTargetId') is not None:check(remote['runTargetId']==workshop,'Task target differs from workshop')
        for row in outputs.get('generated',[]):
            if row.get('source')!='generated':continue
            child=row.get('nodeId')
            if child is not None:check(child==workshop,'Child output belongs to another workshop')
            else:
                check(parent==workshop and remote.get('runTargetId')==workshop and outputs.get('frozen') is True,
                      'Output identity missing: need frozen parent and matching task target')
            path=Path(row['path'])
            if not path.is_file():raise FileNotFoundError('Reported file temporarily unavailable: '+str(path))
            if row.get('taskId') is not None:check(row['taskId']==run['taskId'],'Output record belongs to another task')
            check(path.resolve().parent==Path(t['output_dir']).resolve(),'Output not from this attempt directory')
            check(path_key(path) not in previous,'Output path existed before this attempt')
            check(path.stat().st_mtime*1000 >= remote['startedAt']-2000,'Output predates current task')
            unique[path_key(path)]=path
        check(unique,'No new generated image for task')
        task_candidates=[]
        input_hashes={ref['sha256'].lower() for ref in t['references']}
        for index, path in enumerate(unique.values(), 1):
            digest=sha(path)
            if digest in input_hashes:
                echoes.append({'id':t['id'],'task_id':run['taskId'],'path':str(path.resolve()),
                               'sha256':digest,'input_echo':True,
                               'matched_references':[ref['path'] for ref in t['references'] if ref['sha256'].lower()==digest]})
                continue
            rejected_record={'id':t['id'],'candidate_id':f"{t['id']}-candidate-{index}",
                             'task_id':run['taskId'],'path':str(path.resolve()),'sha256':digest}
            try:
                with Image.open(path) as im:im.load();width,height=im.size
            except (FileNotFoundError,PermissionError):
                raise  # Temporary local I/O remains recoverable, not a permanent rejection.
            except (OSError,ValueError) as exc:
                rejected.append(dict(rejected_record,reason='decode_error',error_type=type(exc).__name__))
                continue
            a,b=map(int,t['aspect_ratio'].split(':'))
            if abs((width/height)/(a/b)-1)>0.03:
                rejected.append(dict(rejected_record,reason='ratio_mismatch',width=width,height=height,expected_ratio=t['aspect_ratio']))
                continue
            row={'id':t['id'],'candidate_id':f"{t['id']}-candidate-{index}",'task_id':run['taskId'],'workshop_id':workshop,'path':str(path.resolve()),'sha256':digest,'width':width,'height':height,'prompt_sha256':t['prompt_sha256'],'started_at':remote.get('startedAt'),'ended_at':remote.get('endedAt'),'duration_ms':remote.get('durationMs'),'visual_status':'needs_agent_review'}
            task_candidates.append(row)
        if not task_candidates and any(r['id']==t['id'] for r in rejected):
            dest.mkdir(parents=True)
            (dest/'candidate-audit.json').write_text(json.dumps({'technical_status':'no_valid_candidates',
                'rejected_candidates':rejected,'echoes':echoes,'generation_retry_authorized':False},ensure_ascii=False,indent=2),encoding='utf-8')
            raise ValueError(f"No valid generated candidate for {t['id']}; inspect {dest/'candidate-audit.json'}; no regeneration authorized")
        check(task_candidates,f"No new image for task {t['id']}: all returned files are input echoes; originals preserved, no retry authorized")
        candidates.extend(task_candidates)
        chosen=state.get('selected_candidates',{}).get(t['id'])
        if chosen is not None:
            check(isinstance(chosen,dict) and evidence(chosen.get('evidence')) and isinstance(chosen.get('path'),str) and isinstance(chosen.get('sha256'),str), 'Selection requires path, sha256 and review evidence')
            selected=[r for r in task_candidates if path_key(r['path'])==path_key(chosen['path']) and r['sha256']==chosen['sha256'].lower()]
            check(len(selected)==1,'Selected candidate is not a verified result')
            records.append(selected[0])
        elif len(task_candidates)==1: records.append(task_candidates[0])
        else: pending.append(t['id'])
    dest.mkdir(parents=True)
    for row in candidates:
        with Image.open(row['path']) as im:
            im.convert('RGB').resize((min(im.width,512),round(im.height*min(im.width,512)/im.width)),Image.Resampling.LANCZOS).save(dest/(row['candidate_id']+'-inspection.jpg'),quality=93)
    result={'technical_status':'outputs_verified','visual_status':'needs_agent_review','images':records,'candidates':candidates,'echoes':echoes,'rejected_candidates':rejected,'selection_required':pending,
            'prompt_transport':{t['id']:t.get('prompt_normalization','unchanged') for t in package['tasks']}}
    (dest/'agent-return.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('compile');p.add_argument('manifest');p.add_argument('output')
    p=sub.add_parser('readback');p.add_argument('package');p.add_argument('readbacks')
    p=sub.add_parser('readback-export');p.add_argument('package');p.add_argument('snapshot');p.add_argument('id_map');p.add_argument('output')
    p=sub.add_parser('reconcile');p.add_argument('package');p.add_argument('state');p.add_argument('snapshot');p.add_argument('output')
    args=parser.parse_args()
    try:
        if args.command=='compile':result=compile_tasks(read(args.manifest),args.output,Path(args.manifest).resolve().parent)
        elif args.command=='readback':result=assert_readback(read(args.package),read(args.readbacks))
        elif args.command=='readback-export':result=readback_export(args.package,args.snapshot,args.id_map,args.output)
        else:result=reconcile(read(args.package),read(args.state),read(args.snapshot),args.output)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as error:parser.exit(2,str(error)+'\n')


if __name__=='__main__':main()
