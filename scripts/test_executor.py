"""Stateful fake-server regressions. Never contacts a real model or Starcanvas."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from PIL import Image
import test_audit_regressions as fixtures
from starcanvas_adapter import compile_tasks, sha
import starcanvas_executor as runtime
from starcanvas_executor import Executor, REQUIRED, run_lock
from starcanvas_mcp import TransportError
from test_fixtures import bind_review_fixture


class FakeClock:
    def __init__(self):self.now=time.time()
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class FakeServer:
    server={'serverInfo':{'name':'fake-starcanvas','version':'offline'}}
    def __init__(self,clock):
        self.clock=clock;self.rev=0;self.nodes={};self.links=[];self.mapping={}
        self.project='fixture-project';self.tasks={};self.calls=[];self.submissions=[]
        self.drop_response=False;self.missing_ids=False;self.ambiguous=False
        self.fail_nodes=set();self.no_output_nodes=set();self.echo_nodes=set()
        self.extra_reference_nodes=set();self.polls_to_done=2
        self.block_preflight=False;self.materialize=True

    def resource(self,uri):return 'Fake workflow guide for offline testing'
    def tools(self):return [{'name':x} for x in REQUIRED]
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def close(self):pass

    def refresh(self):
        for wid,node in self.nodes.items():
            if node['type']!='image/workshop':continue
            gens=[a for a,b in self.links if b==wid]
            if not gens:continue
            gen=self.nodes[gens[0]]
            loaders=[a for a,b in self.links if b==gens[0]]
            if not loaders:continue
            loader=self.nodes[loaders[0]]
            if not loader.get('images') or not self.materialize:continue
            row=node.setdefault('rows',[{'id':wid+'-row','seq':1,'source':'gpt-image','params':{}}])[0]
            row.update(prompt=gen['prompt'],images=[x['path'] for x in loader['images']],
                       saveDir=node.get('autoSavePath',''),saveFilled=bool(node.get('autoSavePath')))
            row.setdefault('params',{}).update({k:v for k,v in {
                'model':gen['modelType'],'resolution':gen['resolution'],'quality':gen['quality'],
                'aspectRatio':gen['aspectRatio'],'gptStyle':'sunburst','transparent':False}.items() if k not in row['params']})

    def call(self,name,args):
        self.calls.append((name,copy.deepcopy(args)))
        data={}
        if name=='workspace_get_context':data={'batchProjectId':self.project,'batchRevision':self.rev}
        elif name=='model_get_capabilities':data={'accountAvailable':True,'kinds':['image']}
        elif name=='project_create':
            self.rev=1
            return {'ok':True,'data':{'projectId':self.project},'meta':{'revision':0}}
        elif name=='canvas_get_summary':data={'projectId':self.project,'revision':self.rev}
        elif name=='canvas_get_node':data={'node':copy.deepcopy(self.nodes[args['nodeId']]),'incoming':[],'outgoing':[]}
        elif name=='workflow_apply_patch':
            if args.get('expectedRevision')!=self.rev:raise ValueError('revision mismatch')
            if args.get('dryRun'):data={'dryRun':True,'blocked':False}
            else:
                created={}
                for op in args['operations']:
                    if op['op']=='createNode':
                        nid='node-'+str(len(self.nodes)+1)
                        self.mapping[op['clientRef']]=nid;created[op['clientRef']]=nid
                        self.nodes[nid]=dict(op.get('data',{}),id=nid,type=op['type'])
                        self.nodes[nid].update(x=op.get('x',0),y=op.get('y',0))
                        if op['type']=='image/workshop':self.nodes[nid]['autoSaveEnabled']=True
                    elif op['op']=='connect':self.links.append((self.mapping[op['fromRef']],self.mapping[op['toRef']]))
                    elif op['op']=='updateNode':self.nodes[op['nodeId']].update(copy.deepcopy(op['data']))
                self.refresh();self.rev+=1;data={'idMap':created}
        elif name=='canvas_attach_local_images':
            if args.get('expectedRevision')!=self.rev:raise ValueError('revision mismatch')
            if not args.get('dryRun'):
                node=self.nodes[args['nodeId']]
                if args['kind']=='image':
                    values=[{'path':p} for p in args['paths']]
                    node['images']=values if args.get('replace') else node.get('images',[])+values
                else:
                    node['autoSavePath']=args['folderPath'];Path(args['folderPath']).mkdir(parents=True,exist_ok=True)
                self.refresh();self.rev+=1
            data={'blocked':False}
        elif name=='canvas_prepare_run':
            items=[]
            for wid in args['nodeIds']:
                node=self.nodes[wid];rows=node.get('rows',[])
                if not rows:continue
                row=rows[0]
                node['runPreparation']={'id':'prep-'+wid,'digest':'digest-'+wid,'goal':'save'}
                request=dict(row['params'],prompt=row['prompt'],images=row['images'],saveDir=row['saveDir'])
                items.append({'nodeId':wid,'ready':True,'preparationId':'prep-'+wid,'requestDigest':'digest-'+wid,
                              'rows':[{'rowId':row['id'],'ready':True,'effectiveRequest':request}]})
            data={'generationSubmitted':False,'items':items}
        elif name=='project_export':
            Path(args['path']).write_text(json.dumps({'canvas':{'nodes':list(self.nodes.values())}}),encoding='utf-8')
            data={'path':args['path']}
        elif name=='run_preflight':data={'blocked':self.block_preflight,'issues':[]}
        elif name=='canvas_run_node':
            nodes=args['nodeIds'];self.submissions.append(list(nodes));runs=[]
            for wid in nodes:
                tid='task-'+str(len(self.tasks)+1)
                self.tasks[tid]={'id':tid,'projectId':self.project,'runMode':'target','runTargetId':wid,
                    'startedAt':round(self.clock()*1000),'endedAt':None,'status':'running','outputs':{'generated':[]},'_polls':0}
                runs.append({'nodeId':wid,'taskId':tid,'status':'running'})
                if self.ambiguous:
                    other='task-'+str(len(self.tasks)+1);self.tasks[other]=dict(self.tasks[tid],id=other)
            if self.drop_response:
                self.drop_response=False;raise TransportError('synthetic lost acknowledgement')
            data={'runs':[{'nodeId':r['nodeId'],'status':'not_started'} for r in runs] if self.missing_ids else runs}
        elif name=='task_list':data={'items':[copy.deepcopy(x) for x in self.tasks.values()],'nextCursor':None}
        elif name=='task_get':
            remote=self.tasks[args['taskId']];remote['_polls']+=1;wid=remote['runTargetId']
            if remote['_polls']>=self.polls_to_done:
                remote['status']='error' if wid in self.fail_nodes else 'done'
                remote['endedAt']=round(self.clock()*1000)
                if remote['status']=='done' and wid not in self.no_output_nodes and not remote['outputs']['generated']:
                    row=self.nodes[wid]['rows'][0];file=Path(row['saveDir'])/'result.png'
                    if wid in self.echo_nodes:file.write_bytes(Path(row['images'][0]).read_bytes())
                    else:
                        a,b=map(int,row['params']['aspectRatio'].split(':'))
                        Image.new('RGB',(a*10,b*10),(100,len(self.tasks)%200,25)).save(file)
                    os.utime(file,(self.clock(),self.clock()))
                    record={'source':'generated','nodeId':wid,'taskId':remote['id'],'path':str(file)}
                    remote['outputs']={'generated':[record,record]}
            data=copy.deepcopy(remote)
        else:raise AssertionError('Unexpected tool '+name)
        return {'ok':True,'data':data,'meta':{'projectId':self.project,'revision':self.rev}}


class ExecutorTests(unittest.TestCase):
    def test_native_parent_output_schema_completes_without_resubmission(self):
        self.prepare(3);original=self.server.call
        def native_call(name,args):
            response=original(name,args)
            if name=='task_get':
                remote=response['data'];remote['outputs'].update(nodeId=remote['runTargetId'],frozen=True)
                for row in remote['outputs'].get('generated',[]):row.pop('nodeId',None)
            return response
        self.server.call=native_call
        result=self.worker.run(execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual(len(self.server.submissions),1)

    def test_project_names_show_stage_actual_count_and_repair_ids(self):
        self.prepare(10)
        name=self.worker.state['project_name']
        self.assertIn('正式页·9比16·10张',name)
        created=next(a for n,a in self.server.calls if n=='project_create')
        self.assertEqual(created['name'],name)
        package=copy.deepcopy(self.worker.package)
        package['ready_stage']='repair';package['tasks']=[package['tasks'][0],package['tasks'][8]]
        self.assertIn('返修·01、09·2张',runtime.project_name(package,'abcdefghi'))
        self.assertNotEqual(runtime.project_name(package,'abcdefghi'),runtime.project_name(package,'123456789'))
        package['ready_stage']='master';package['tasks']=[dict(package['tasks'][0],kind='master')]
        self.assertIn('母版·9比21·1张',runtime.project_name(package,'abcdefghi'))

    def setUp(self):
        f=fixtures.AuditRegressions();f.setUp();self.root=f.root;self.manifest=f.m
        self.clock=FakeClock();self.server=FakeServer(self.clock)
        self.folder=self.root/'run';self.folder.mkdir()
        self.worker=Executor(self.server,self.folder,clock=self.clock,sleep=self.clock.sleep)

    def prepare(self,count=3):
        self.manifest['tasks']=[dict(copy.deepcopy(self.manifest['tasks'][0]),id=f'screen-{i:02d}') for i in range(1,count+1)]
        bind_review_fixture(self.manifest,self.root)
        p=compile_tasks(self.manifest,self.root/'package')['package']
        result=self.worker.prepare(p)
        self.assertEqual(result['status'],'prepared')
        return p

    def test_prepare_is_non_generating_and_all_pages_submit_before_poll(self):
        self.prepare(8);self.assertFalse(self.server.submissions)
        result=self.worker.run(execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual(result['counts'],{'verified':8})
        self.assertEqual(len(self.server.submissions),1);self.assertEqual(len(self.server.submissions[0]),8)
        first_poll=next(i for i,(name,_) in enumerate(self.server.calls) if name=='task_get')
        self.assertEqual(len(self.server.tasks),8)
        self.assertTrue(any(name=='canvas_run_node' and len(args['nodeIds'])==8 for name,args in self.server.calls[:first_poll]))
        self.assertTrue(all(args.get('replace') is True for name,args in self.server.calls if name=='canvas_attach_local_images' and args['kind']=='image'))

    def test_execute_flag_required(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'--execute'):self.worker.run()
        self.assertFalse(self.server.submissions)

    def test_wrong_workshop_parameters_block_before_submit(self):
        self.prepare()
        wid=self.worker.state['tasks']['screen-01']['node_id']
        self.server.nodes[wid]['rows'][0]['params']['model']='gpt-image-2-4k-qy'
        result=self.worker.run(execute=True)
        self.assertEqual(result['status'],'blocked');self.assertFalse(self.server.submissions)

    def test_extra_references_block_before_submit(self):
        self.prepare()
        loader=self.worker.state['id_map']['screen-01-load']
        self.server.nodes[loader]['images'].append({'path':str(self.root/'master.png')})
        result=self.worker.run(execute=True)
        self.assertEqual(result['status'],'blocked');self.assertFalse(self.server.submissions)

    def test_missing_materialized_row_does_not_trigger_probe_generation(self):
        self.server.materialize=False
        with self.assertRaisesRegex(ValueError,'preparation'):self.prepare()
        self.assertFalse(self.server.submissions);self.assertEqual(self.worker.state['status'],'preparation_failed')

    def test_preflight_error_does_not_submit(self):
        self.prepare();self.server.block_preflight=True
        self.assertEqual(self.worker.run(execute=True)['status'],'blocked')
        self.assertFalse(self.server.submissions)

    def test_native_prepared_node_save_path_supported(self):
        self.prepare()
        for node in self.server.nodes.values():
            if node['type']=='image/workshop':
                node['rows'][0].pop('saveDir');node['rows'][0].pop('saveFilled')
        self.worker.verify_snapshot()

    def test_preparation_identity_drift_blocks(self):
        self.prepare()
        wid=self.worker.state['tasks']['screen-01']['node_id']
        self.server.nodes[wid]['runPreparation']['id']='other-preparation'
        self.assertEqual(self.worker.run(execute=True)['status'],'blocked')
        self.assertFalse(self.server.submissions)

    def test_conflicting_node_save_path_blocks(self):
        self.prepare()
        wid=self.worker.state['tasks']['screen-01']['node_id']
        self.server.nodes[wid]['autoSavePath']=str(self.root/'wrong')
        self.assertEqual(self.worker.run(execute=True)['status'],'blocked')
        self.assertFalse(self.server.submissions)

    def test_lost_ack_recovers_by_exact_workshop_without_second_submission(self):
        self.prepare();self.server.drop_response=True
        result=self.worker.run(execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review');self.assertEqual(len(self.server.submissions),1)
        self.assertEqual(len({t['task_id'] for t in self.worker.state['tasks'].values()}),3)

    def test_not_started_without_id_can_recover_an_actual_task(self):
        self.prepare();self.server.missing_ids=True
        self.assertEqual(self.worker.run(execute=True,max_wait=10,poll_interval=1)['status'],'complete_needs_review')
        self.assertEqual(len(self.server.submissions),1)

    def test_ambiguous_missing_ack_stops_without_guess_or_resubmit(self):
        self.prepare(1);self.server.missing_ids=True;self.server.ambiguous=True
        result=self.worker.run(execute=True,max_wait=2,poll_interval=1)
        self.assertEqual(result['status'],'submission_unknown')
        self.assertIsNone(self.worker.state['tasks']['screen-01']['task_id']);self.assertEqual(len(self.server.submissions),1)
        resumed=Executor(self.server,self.folder,clock=self.clock,sleep=self.clock.sleep)
        resumed.run(resume=True,max_wait=1,poll_interval=1)
        self.assertEqual(len(self.server.submissions),1)

    def test_foreign_task_in_same_project_is_not_bound(self):
        self.prepare(1)
        self.server.tasks['foreign']={'id':'foreign','projectId':self.server.project,'runMode':'target',
            'runTargetId':'other-workshop','startedAt':round(self.clock()*1000),'status':'running'}
        self.server.missing_ids=True
        self.worker.run(execute=True,max_wait=10,poll_interval=1)
        self.assertNotEqual(self.worker.state['tasks']['screen-01']['task_id'],'foreign')

    def test_failure_is_partial_not_success_and_other_pages_finish(self):
        self.prepare();self.server.fail_nodes.add(self.worker.state['tasks']['screen-02']['node_id'])
        result=self.worker.run(execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'partial_failure');self.assertEqual(result['counts'],{'verified':2,'failed':1})
        self.assertEqual(len(self.server.submissions),1)
        self.assertEqual(self.worker.state['tasks']['screen-02']['status'],'failed')

    def test_done_without_file_times_out_and_resume_never_resubmits(self):
        self.prepare(1);wid=self.worker.state['tasks']['screen-01']['node_id'];self.server.no_output_nodes.add(wid)
        result=self.worker.run(execute=True,max_wait=2,poll_interval=1)
        self.assertEqual(result['status'],'timed_out');self.assertEqual(result['counts'],{'awaiting_output':1})
        self.server.no_output_nodes.clear()
        resumed=Executor(self.server,self.folder,clock=self.clock,sleep=self.clock.sleep)
        self.assertEqual(resumed.run(resume=True,max_wait=2,poll_interval=1)['status'],'complete_needs_review')
        self.assertEqual(len(self.server.submissions),1)

    def test_echo_only_is_invalid_and_is_not_automatically_retried(self):
        self.prepare(1);self.server.echo_nodes.add(self.worker.state['tasks']['screen-01']['node_id'])
        result=self.worker.run(execute=True,max_wait=5,poll_interval=1)
        self.assertEqual(result['status'],'partial_failure');self.assertEqual(result['counts'],{'output_invalid':1})
        self.assertEqual(len(self.server.submissions),1)

    def test_known_concurrency_limit_submits_ready_slots_not_trial_pair(self):
        self.prepare(5)
        result=self.worker.run(execute=True,max_wait=10,poll_interval=1,max_in_flight=2)
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual([len(x) for x in self.server.submissions],[2,2,1])
        self.assertEqual(len({x for batch in self.server.submissions for x in batch}),5)

    def test_state_crash_window_and_repeat_run_do_not_duplicate(self):
        self.prepare(1)
        self.worker.state.update(submission_authorized=True,max_in_flight=1)
        self.worker.submit(['screen-01'])
        with self.assertRaisesRegex(ValueError,'already started'):self.worker.run(execute=True)
        resumed=Executor(self.server,self.folder,clock=self.clock,sleep=self.clock.sleep)
        self.assertEqual(resumed.run(resume=True,max_wait=10,poll_interval=1)['status'],'complete_needs_review')
        self.assertEqual(len(self.server.submissions),1)

    def test_task_binding_mismatch_blocks_result(self):
        self.prepare(1);self.server.polls_to_done=10
        self.worker.run(execute=True,max_wait=0)
        tid=self.worker.state['tasks']['screen-01']['task_id']
        self.server.tasks[tid]['runTargetId']='wrong-workshop'
        self.assertEqual(self.worker.run(resume=True,max_wait=1)['status'],'blocked')
        self.assertEqual(len(self.server.submissions),1)

    def test_existing_output_and_mutated_package_cannot_be_reused(self):
        self.prepare(1)
        p=self.folder/'package.json';data=json.loads(p.read_text(encoding='utf-8'));data['authority']='changed'
        p.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'package changed'):self.worker.run(execute=True)
        self.assertFalse(self.server.submissions)

    def test_os_lock_prevents_two_owners(self):
        with run_lock(self.folder):
            with self.assertRaises(ValueError):
                with run_lock(self.folder):pass

    def test_direct_submit_without_authority_is_blocked(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'not authorized'):self.worker.submit(['screen-01'])
        self.assertFalse(self.server.submissions)

    def test_cli_failure_returns_nonzero(self):
        package=self.prepare(2)
        self.server.fail_nodes.add(self.worker.state['tasks']['screen-02']['node_id'])
        self.server.polls_to_done=1
        args=['executor','--connection','local-secret-config.json','run',package,str(self.folder),'--execute','--max-wait','0']
        with patch.object(runtime,'StdioMCP',return_value=self.server),patch.object(runtime,'load_connection',return_value={}),patch('sys.argv',args),redirect_stdout(io.StringIO()) as output:
            code=runtime.main()
        self.assertEqual(code,2);self.assertIn('partial_failure',output.getvalue())

    def test_multiple_candidates_select_locally_without_resubmission(self):
        self.prepare(1);wid=self.worker.state['tasks']['screen-01']['node_id']
        self.server.no_output_nodes.add(wid)
        self.worker.run(execute=True,max_wait=0)
        tid=self.worker.state['tasks']['screen-01']['task_id'];remote=self.server.tasks[tid]
        directory=Path(self.worker.package['tasks'][0]['output_dir']);records=[]
        for n,color in enumerate(('green','red')):
            file=directory/f'candidate-{n}.png';Image.new('RGB',(90,160),color).save(file)
            os.utime(file,(self.clock(),self.clock()))
            records.append({'source':'generated','nodeId':wid,'taskId':tid,'path':str(file)})
        remote.update(status='done',endedAt=round(self.clock()*1000),outputs={'generated':records})
        result=self.worker.run(resume=True,max_wait=0)
        self.assertEqual(result['status'],'selection_required')
        result=Executor(None,self.folder).select_candidates({'screen-01':{'path':records[1]['path'],'sha256':sha(records[1]['path']),'evidence':'offline reviewed candidate'}})
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual(len(self.server.submissions),1)


if __name__=='__main__':unittest.main(verbosity=2)
