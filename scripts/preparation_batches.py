"""Bounded, durable node creation. Preparation never authorizes image generation."""
import hashlib
import json
from starcanvas_adapter import check,read,sha


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def page_batches(tasks,operations,limit=80):
    check(type(limit) is int and 1<=limit<=80,'Preparation limit must be 1..80')
    groups=[];claimed=set()
    for task in tasks:
        refs={task[k] for k in ('load_ref','gen_ref','workshop_ref')}
        if task.get('note_ref'):refs.add(task['note_ref'])
        indices=[i for i,op in enumerate(operations) if op.get('clientRef') in refs or op.get('fromRef') in refs]
        group=[operations[i] for i in indices]
        check(group and len(group)<=limit,'A page chain exceeds the preparation limit')
        check(not claimed.intersection(indices),'Overlapping page operation groups')
        check(all(op.get('op')=='createNode' or (op.get('op')=='connect' and op.get('toRef') in refs) for op in group),
              'Preparation cannot split cross-page or unknown operations')
        claimed.update(indices);groups.append(group)
    check(claimed==set(range(len(operations))),'Unassigned preparation operations')
    batches=[];batch=[]
    for group in groups:
        if batch and len(batch)+len(group)>limit:batches.append(batch);batch=[]
        batch.extend(group)
    if batch:batches.append(batch)
    return batches


def create_nodes(worker,operations,existing_ids):
    from starcanvas_executor import atomic_json
    batches=page_batches(worker.package['tasks'],operations)
    saved=worker.state.setdefault('node_batches',[])
    if not saved:
        saved.extend({'index':i,'digest':digest(ops),'status':'pending'} for i,ops in enumerate(batches))
        worker.save()
    check(len(saved)==len(batches),'Preparation batch plan changed')
    for entry,ops in zip(saved,batches):
        check(entry['digest']==digest(ops),'Preparation operations changed during recovery')
        expected={op['clientRef'] for op in ops if op['op']=='createNode'}
        ack_path=worker.folder/f"node-batch-{entry['index']}-ack.json"
        if entry['status']=='complete':
            check(ack_path.is_file() and sha(ack_path)==entry['ack_sha256'],'Completed node acknowledgement changed')
            check(all(k in worker.state['id_map'] for k in expected),'Completed batch lost its mapping')
            continue
        # An acknowledgement survives a crash between the remote reply and state save.
        if ack_path.exists():
            ack=read(ack_path)
        else:
            check(entry['status']=='pending','Node creation outcome unknown; inspect the original canvas, never recreate it')
            summary=worker.call('canvas_get_summary',{'projectId':worker.state['project_id']})
            worker.state['revision']=summary['revision']
            args={'projectId':worker.state['project_id'],'expectedRevision':worker.state['revision'],'operations':ops}
            preview=worker.call('workflow_apply_patch',dict(args,dryRun=True))
            check(not preview.get('blocked') and not any(x.get('severity')=='error' for x in preview.get('issues',[])),
                  'Preparation batch preview blocked')
            entry['status']='intent_saved';worker.save()
            reply=worker.call('workflow_apply_patch',dict(args,dryRun=False,
                idempotencyKey=worker.state['run_id']+'-create-nodes-'+str(entry['index'])))
            ack={'operations_digest':entry['digest'],'idMap':reply.get('idMap'),'revision':worker.state['revision']}
            atomic_json(ack_path,ack)
        check(ack.get('operations_digest')==entry['digest'],'Node acknowledgement is for a different batch')
        mapping=ack.get('idMap')
        check(isinstance(mapping,dict) and set(mapping)==expected and all(isinstance(x,str) and x for x in mapping.values())
              and len(set(mapping.values()))==len(expected),'Invalid per-batch node mapping')
        check(not set(mapping.values()).intersection(existing_ids),'Node mapping reused original nodes')
        check(not set(mapping.values()).intersection(worker.state['id_map'].values()),'Node mapping reused another batch')
        # Observe the mapped nodes before accepting a recovered acknowledgement.
        snapshot,_=worker.snapshot('node-batch-verified')
        nodes={n['id']:dict(n,**n.get('data',{})) for n in snapshot['canvas']['nodes']}
        for op in ops:
            if op['op']!='createNode':continue
            node=nodes.get(mapping[op['clientRef']],{})
            check(node.get('type')==op['type'],'Created node missing or wrong type')
            check(all(node.get(k)==v for k,v in op.get('data',{}).items()),'Created node configuration differs')
        worker.state['id_map'].update(mapping)
        entry.update(status='complete',ack_sha256=sha(ack_path));worker.save()
    return worker.state['id_map']
