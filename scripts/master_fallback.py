"""At most three master attempts; never retry unknown, cancelled or successful tasks."""
import copy
import re
import uuid
from pathlib import Path
from starcanvas_adapter import read,compile_tasks,check,transport_prompt,sha

def service_503(value):
    if isinstance(value,dict):
        return any(service_503(value[k]) for k in ('code','statusCode','httpStatus','message','error') if k in value)
    if type(value) is int:return value==503
    return isinstance(value,str) and re.search(r'(?<!\d)503(?!\d)',value) is not None

def error_text(value):
    if isinstance(value,dict):
        return ' '.join(error_text(value[k]) for k in ('code','statusCode','httpStatus','message','error','detail') if k in value)
    return str(value) if isinstance(value,(str,int)) and not isinstance(value,bool) else ''

def service_failure(value):
    text=error_text(value).lower()
    if re.search(r'cancel(?:l)?(?:ed|ation|ing)?|aborted|insufficient[\s_-]*funds|payment[\s_-]*(?:required|failed|declined)|timed?[\s_-]*out|timeout|超时|中止|终止',text):return False
    if re.search(r'(?<!\d)(401|403|402|429)(?!\d)|unauthoriz|authentication|invalid.?api.?key|invalid.?token|forbidden|quota|balance|credit|billing|rate[\s_-]*limit|too\s+many\s+requests|throttl|content.?policy|moderation|余额|额度|欠费|鉴权|认证|权限|审核|取消|限流|频率|请求过多',text):return False
    return bool(re.search(r'(?<!\d)(500|502|503|504)(?!\d)|upstream\s+(?:model\s+)?service\s+error|upstream\s+model\s+error|service\s+unavailable|上游.{0,12}(?:服务|模型).{0,8}(?:错误|异常|失败)|(?:模型|通道)服务.{0,8}(?:错误|异常|不可用)',text))

def eligible(worker):
    if worker.state.get('status')!='partial_failure' or len(worker.state.get('tasks',{}))!=1:return False
    sid,local=next(iter(worker.state['tasks'].items()))
    if local.get('status')!='failed' or not local.get('task_id'):return False
    remote=read(worker.folder/'tasks'/(sid+'.json'))
    if (remote.get('id')!=local['task_id'] or remote.get('runTargetId')!=local['node_id']
        or remote.get('projectId')!=worker.state['project_id'] or remote.get('runMode')!='target'
        or remote.get('status') not in ('error','failed') or not remote.get('endedAt')
        or remote.get('outputs',{}).get('generated')):return False
    error={'error':remote.get('error'),'message':remote.get('note')}
    if service_failure(error):return True  # Frozen task-specific evidence.
    # project_export intentionally omits runtime row.error on the observed server.
    # A live error must be bound to this dedicated workshop and prepared row;
    # never borrow an error from a different execution or an edited request.
    from starcanvas_executor import atomic_json
    from starcanvas_mcp import ToolError,TransportError
    record={'task_id':local['task_id'],'node_id':local['node_id'],'project_id':worker.state['project_id']}
    path=worker.folder/('fallback-node-error-'+uuid.uuid4().hex+'.json')
    def decide(allowed,reason):
        record.update(eligible=allowed,reason=reason);atomic_json(path,record)
        return allowed
    try:
        worker.snapshot('fallback-error')  # Configuration evidence only.
        data=worker.call('canvas_get_node',{'projectId':worker.state['project_id'],'nodeId':local['node_id']})
        record['node_response']=data
        node=data.get('node',{});actual=dict(node,**node.get('data',{}))
        if actual.get('id')!=local['node_id'] or actual.get('type')!='image/workshop':return decide(False,'node_identity_mismatch')
        prepared=worker.state.get('preparations',{}).get(sid,{}).get('rows',[])
        rows=actual.get('rows',[])
        if len(prepared)!=1 or len(rows)!=1:return decide(False,'ambiguous_prepared_row')
        row=rows[0];expected=prepared[0];request=expected.get('effectiveRequest',{})
        if row.get('id')!=expected.get('rowId') or not expected.get('rowId'):return decide(False,'prepared_row_identity_mismatch')
        if row.get('status') not in ('error','failed') or row.get('result'):return decide(False,'row_not_failed_without_output')
        if row.get('prompt')!=request.get('prompt') or row.get('images')!=request.get('images'):
            return decide(False,'row_inputs_changed')
        if any(k not in request or row.get('params',{}).get(k)!=request[k]
               for k in ('model','gptStyle','resolution','aspectRatio','quality','transparent')):
            return decide(False,'row_parameters_changed')
        matches=[t for t in worker.list_tasks() if t.get('runTargetId')==local['node_id']]
        record['workshop_task_ids']=[t.get('id') for t in matches]
        if (len(matches)!=1 or matches[0].get('id')!=local['task_id']
                or matches[0].get('projectId')!=worker.state['project_id'] or matches[0].get('runMode')!='target'):
            return decide(False,'workshop_reused_or_task_unverified')
        error['detail']=row.get('error')
        allowed=service_failure(error)
        return decide(allowed,'bound_row_service_failure' if allowed else 'no_eligible_service_error')
    except (ToolError,TransportError,ValueError,KeyError,TypeError) as exc:
        record['read_error_type']=type(exc).__name__
        return decide(False,'live_error_evidence_unavailable')

def prepare_child_package(worker,tier):
    """Finish only a deterministic unsubmitted package; never replace an attempt."""
    root=worker.folder
    manifest=copy.deepcopy(worker.package);task=manifest['tasks'][0]
    task.update(master_fallback_tier=tier,model_id='gpt-image-2.5-1k-qy' if tier==1 else 'gpt-image-2.5-wd',
                resolution='1K',aspect_ratio='9:16' if tier==2 else '9:21')
    if tier==2:
        source=task['prompt_path'];text=transport_prompt(task)
        prompt_file=root/'fallback-stable-prompt.txt'
        content=text+'\n\n执行参数覆盖（不作为画面文字）：本次稳定通道母版采用9:16竖幅，覆盖前文的画布比例描述。已确认的消费端文案、产品事实、配色和内容不变。'
        if prompt_file.exists():
            check(prompt_file.read_bytes()==content.encode('utf-8'),'Interrupted stable prompt differs; preserve for inspection')
        else:
            prompt_file.write_bytes(content.encode('utf-8'))
        task.update(prompt_path=str(prompt_file),fallback_source_prompt_sha256=sha(source))
        task.pop('prompt_sha256',None);task.pop('transport_prompt_sha256',None)
    manifest['ready_stage']='master';manifest['master_fallback_parent']=str(root)
    start=worker.package['tasks'][0].get('master_fallback_tier',0)
    remaining=worker.package.get('master_fallback',{}).get('max_attempts',3-start)-(tier-start)
    manifest['master_fallback']={'enabled':True,'max_attempts':min(3-tier,max(1,remaining))}
    return compile_tasks(manifest,root/('fallback-package-'+str(tier)),reuse_preparation=True,
                         require_review_binding='review_binding_version' in worker.package)['package']


def run_chain(worker,execute=False,resume=False,**options):
    from starcanvas_executor import Executor,atomic_json,run_lock
    root=worker.folder;record=root/'fallback-chain.json'
    check(not worker.package.get('master_fallback_parent'),'Resume the original master run recorded by master_fallback_parent, not its child')
    policy=worker.package.get('master_fallback',{})
    if not policy.get('enabled') or any(t['kind']!='master' for t in worker.package['tasks']):
        return worker.run(execute=execute,resume=resume,**options)
    check(len(worker.package['tasks'])==1,'One master per fallback chain')
    start_tier=worker.package['tasks'][0].get('master_fallback_tier',0)
    configured_limit=policy.get('max_attempts',3-start_tier)
    check(type(configured_limit) is int and 1<=configured_limit<=3-start_tier,'Invalid master max_attempts')
    attempt_limit=min(configured_limit,worker.package.get('repair_authorization',{}).get('max_generations',3))
    worker.verify_frozen()
    if record.exists():
        check(resume or (execute and worker.state['status']=='prepared' and not worker.state.get('batches')),
              'Master chain already exists; resume original run instead of resubmitting')
        chain=read(record)
        saved_limit=chain.get('max_attempts',attempt_limit)
        check(type(saved_limit) is int and 1<=saved_limit<=3-start_tier,'Invalid recorded attempt limit')
        attempt_limit=min(attempt_limit,saved_limit)
        check(worker.state.get('submission_authorized') is True or (execute and worker.state['status']=='prepared'),
              'Original master submission was not authorized')
    else:
        chain={'attempts':[{'tier':start_tier,'folder':str(root)}],'max_attempts':attempt_limit}
        atomic_json(record,chain)
    check([a.get('tier') for a in chain['attempts']]==list(range(start_tier,start_tier+len(chain['attempts'])))
          and 1<=len(chain['attempts'])<=attempt_limit,'Invalid fallback attempt sequence or allowance exceeded')
    while True:
        entry=chain['attempts'][-1];tier=entry['tier']
        check(type(tier) is int and start_tier<=tier<=2,'Invalid fallback tier')
        expected=root if tier==start_tier else root/('fallback-'+str(tier))
        check(Path(entry['folder']).resolve()==expected.resolve(),'Invalid fallback state')
        if tier!=start_tier:
            expected.mkdir(exist_ok=True)
        current=worker if tier==start_tier else Executor(worker.client,expected,clock=worker.clock,sleep=worker.sleep,progress=worker.progress)
        def advance():
            if current.state is None:
                path=prepare_child_package(worker,tier)
                entry['package']=path;entry['package_sha256']=sha(path)
                atomic_json(record,chain)
                current.prepare(path)
            current.verify_frozen()
            if current.state['status'] in ('preparing','preparation_failed'):
                return current.summary()
            if current.state['status']=='prepared':
                check(worker.package['ready_stage']!='repair' or worker.package.get('repair_authorization_version')==1,
                      'Historical repair cannot start another paid attempt without new repair authorization')
                check(execute or worker.state.get('submission_authorized') is True,'No master execution authority')
                return current.run(execute=True,**options)
            recoverable=any(t['status'] in ('collection_pending','output_invalid') for t in current.state.get('tasks',{}).values())
            if current.state['status'] in ('complete_needs_review','selection_required','partial_failure') and not recoverable:
                return current.summary()
            return current.run(resume=True,**options)
        if tier==start_tier:result=advance()
        else:
            with run_lock(expected):result=advance()
        entry['phase']=result['status']
        chain['result']=dict(result,attempt_count=len(chain['attempts']),selected_tier=tier)
        atomic_json(record,chain)
        atomic_json(root/'report.json',dict(chain['result'],root_attempt=worker.summary(),
                    attempts=chain['attempts'],auto_retries=0,report_kind='master_fallback_chain'))
        if (tier==2 or len(chain['attempts'])>=attempt_limit
                or (worker.package['ready_stage']=='repair' and worker.package.get('repair_authorization_version')!=1)
                or not eligible(current)):return chain['result']
        next_tier=tier+1;folder=root/('fallback-'+str(next_tier));package_folder=root/('fallback-package-'+str(next_tier))
        check(not (folder/'state.json').exists(),'Unrecorded fallback run exists; inspect its submission state')
        chain['attempts'].append({'tier':next_tier,'folder':str(folder),'package':str(package_folder/'package.json'),
                                  'trigger':'confirmed_terminal_service_failure','phase':'preparing'})
        atomic_json(record,chain)  # Intent precedes package/prompt/directory creation.
        worker.progress({'status':'master_channel_fallback','tier':next_tier,'model':'gpt-image-2.5-1k-qy' if next_tier==1 else 'gpt-image-2.5-wd',
                         'resolution':'1K','attempt':len(chain['attempts']),'max_attempts':chain['max_attempts']})
