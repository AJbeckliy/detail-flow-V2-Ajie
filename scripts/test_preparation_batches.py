import copy
import unittest
from unittest.mock import patch
import test_executor as fixtures
import starcanvas_executor as runtime
from starcanvas_adapter import compile_tasks,read
from starcanvas_mcp import TransportError
from preparation_batches import page_batches
from test_fixtures import bind_review_fixture


class PreparationBatchTests(unittest.TestCase):
    def fixture(self,count=16):
        f=fixtures.ExecutorTests();f.setUp()
        f.manifest['tasks']=[dict(copy.deepcopy(f.manifest['tasks'][0]),id=f'screen-{i:02d}') for i in range(1,count+1)]
        bind_review_fixture(f.manifest,f.root)
        path=compile_tasks(f.manifest,f.root/'package')['package']
        original=f.server.call
        def bounded(name,args):
            if name=='workflow_apply_patch' and len(args['operations'])>80:raise ValueError('Platform operation limit 80')
            return original(name,args)
        f.server.call=bounded
        return f,path
    def commits(self,f):
        return [a for n,a in f.server.calls if n=='workflow_apply_patch' and not a.get('dryRun')
                and any(op['op']=='createNode' for op in a['operations'])]
    def test_sixteen_pages_prepare_in_two_batches_but_generate_together(self):
        f,p=self.fixture();f.worker.prepare(p)
        self.assertEqual([len(a['operations']) for a in self.commits(f)],[78,18])
        self.assertFalse(f.server.submissions)
        result=f.worker.run(execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual([len(x) for x in f.server.submissions],[16])
    def test_boundary_thirteen_and_fourteen_pages(self):
        for count,expected in ((13,[78]),(14,[78,6])):
            f,p=self.fixture(count);f.worker.prepare(p)
            self.assertEqual([len(a['operations']) for a in self.commits(f)],expected)
    def test_second_preview_failure_resumes_without_recreating_first(self):
        f,p=self.fixture();original=f.server.call;failed=[False]
        def fail_second(name,args):
            if name=='workflow_apply_patch' and args.get('dryRun') and len(args['operations'])==18 and not failed[0]:
                failed[0]=True;raise ValueError('synthetic second preview failure')
            return original(name,args)
        f.server.call=fail_second
        with self.assertRaises(ValueError):f.worker.prepare(p)
        first=dict(f.worker.state['id_map']);self.assertEqual(len(first),52)
        worker=runtime.Executor(f.server,f.folder,clock=f.clock,sleep=f.clock.sleep)
        self.assertEqual(worker.prepare(p)['status'],'prepared')
        self.assertEqual(read(f.folder/'report.json')['status'],'prepared')
        self.assertEqual({k:worker.state['id_map'][k] for k in first},first)
        self.assertEqual(len(self.commits(f)),2)
        self.assertEqual(sum(n=='project_create' for n,a in f.server.calls),1)
        self.assertFalse(f.server.submissions)
    def test_lost_node_ack_never_recreates_unknown_batch(self):
        f,p=self.fixture();original=f.server.call;lost=[False]
        def lose_ack(name,args):
            result=original(name,args)
            if name=='workflow_apply_patch' and not args.get('dryRun') and any(op['op']=='createNode' for op in args['operations']) and not lost[0]:
                lost[0]=True;raise TransportError('synthetic lost node acknowledgement')
            return result
        f.server.call=lose_ack
        with self.assertRaises(TransportError):f.worker.prepare(p)
        count=len(f.server.nodes)
        with self.assertRaisesRegex(ValueError,'outcome unknown'):
            runtime.Executor(f.server,f.folder).prepare(p)
        self.assertEqual(len(f.server.nodes),count);self.assertEqual(len(self.commits(f)),1)
    def test_persisted_ack_recovers_after_state_save_crash(self):
        f,p=self.fixture();original=runtime.atomic_json;crashed=[False]
        def crash(path,value):
            original(path,value)
            if str(path).endswith('node-batch-0-ack.json') and not crashed[0]:
                crashed[0]=True;raise OSError('synthetic local interruption after ack')
        with patch.object(runtime,'atomic_json',crash),self.assertRaises(OSError):f.worker.prepare(p)
        self.assertEqual(runtime.Executor(f.server,f.folder).prepare(p)['status'],'prepared')
        self.assertEqual(len(self.commits(f)),2)
    def test_unassigned_operation_rejected_instead_of_truncated(self):
        f,p=self.fixture(1);package=read(p);ops=package['operations']+[{'op':'updateNode','nodeId':'foreign','data':{}}]
        with self.assertRaisesRegex(ValueError,'Unassigned'):page_batches(package['tasks'],ops)

if __name__=='__main__':unittest.main()
