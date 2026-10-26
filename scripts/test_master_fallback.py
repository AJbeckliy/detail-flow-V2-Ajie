import json
import unittest
import test_executor as fixture
from master_fallback import run_chain,service_503,service_failure
from starcanvas_adapter import compile_tasks,validate

class MasterFallbackTests(unittest.TestCase):
    def setup_worker(self,fail_count=1,error=503,tier=0,enabled=True):
        f=fixture.ExecutorTests();f.setUp();m=f.manifest
        m['ready_stage']='master';m.pop('visual_master')
        m['tasks'][0].update(kind='master',model_id='gpt-image-2.5-qy',resolution='2K',aspect_ratio='9:21')
        m['master_fallback']={'enabled':enabled}
        if tier:m['tasks'][0].update(master_fallback_tier=tier,model_id='gpt-image-2.5-1k-qy' if tier==1 else 'gpt-image-2.5-wd',resolution='1K',aspect_ratio='9:21' if tier==1 else '9:16')
        original=f.server.call
        def call(name,args):
            if name=='canvas_run_node' and len(f.server.submissions)<fail_count:
                f.server.fail_nodes.update(args['nodeIds'])
            result=original(name,args)
            if name=='task_get' and result['data']['status']=='error':result['data']['error']={'statusCode':error}
            return result
        f.server.call=call
        p=compile_tasks(m,f.root/'package')['package'];f.worker.prepare(p)
        return f
    def run_worker(self,f,resume=False):
        return run_chain(f.worker,execute=not resume,resume=resume,max_wait=10,poll_interval=1)
    def test_first_503_uses_1k_then_stops_on_success(self):
        f=self.setup_worker();result=self.run_worker(f)
        self.assertEqual(result['status'],'complete_needs_review');self.assertEqual(len(f.server.submissions),2)
        p=json.loads((f.folder/'fallback-package-1/package.json').read_text(encoding='utf-8'))
        self.assertEqual(p['tasks'][0]['model_id'],'gpt-image-2.5-1k-qy');self.assertEqual(p['tasks'][0]['aspect_ratio'],'9:21')
        self.assertEqual(self.run_worker(f,True)['status'],'complete_needs_review');self.assertEqual(len(f.server.submissions),2)
    def test_second_503_uses_stable_and_third_failure_stops(self):
        f=self.setup_worker(3);result=self.run_worker(f)
        self.assertEqual(result['status'],'partial_failure');self.assertEqual(len(f.server.submissions),3)
        p=json.loads((f.folder/'fallback-package-2/package.json').read_text(encoding='utf-8'))
        self.assertEqual(p['tasks'][0]['model_id'],'gpt-image-2.5-wd')
        self.assertEqual(p['tasks'][0]['aspect_ratio'],'9:16')
        self.run_worker(f,True);self.assertEqual(len(f.server.submissions),3)
    def test_non503_does_not_switch(self):
        f=self.setup_worker(3,401);self.run_worker(f);self.assertEqual(len(f.server.submissions),1)
    def test_generic_upstream_error_without_code_switches(self):
        f=self.setup_worker(1,'Upstream model service error. Try again later.')
        self.assertEqual(self.run_worker(f)['status'],'complete_needs_review')
        self.assertEqual(len(f.server.submissions),2)
    def test_direct_1k_master_with_fallback_disabled_is_runnable(self):
        f=self.setup_worker(0,tier=1,enabled=False)
        self.assertEqual(self.run_worker(f)['status'],'complete_needs_review');self.assertEqual(len(f.server.submissions),1)
    def test_direct_1k_can_only_fall_to_stable_once(self):
        f=self.setup_worker(3,tier=1)
        self.assertEqual(self.run_worker(f)['status'],'partial_failure');self.assertEqual(len(f.server.submissions),2)
        self.run_worker(f,True);self.assertEqual(len(f.server.submissions),2)
    def test_direct_stable_master_is_runnable(self):
        f=self.setup_worker(0,tier=2,enabled=False)
        self.assertEqual(self.run_worker(f)['status'],'complete_needs_review');self.assertEqual(len(f.server.submissions),1)
    def test_account_errors_override_generic_service_words(self):
        for text in ('Upstream model service error: quota exceeded','503 insufficient credits','503 余额不足','503 unauthorized'):
            self.assertFalse(service_failure(text))
        self.assertTrue(service_failure('Upstream model service error. Try again later.'))
        self.assertFalse(service_failure('Task failed'))
    def test_success_never_switches(self):
        f=self.setup_worker(0);self.run_worker(f);self.assertEqual(len(f.server.submissions),1)
    def test_unknown_submission_does_not_switch(self):
        f=self.setup_worker();f.server.drop_response=True;f.server.ambiguous=True
        result=self.run_worker(f);self.assertEqual(result['status'],'submission_unknown');self.assertEqual(len(f.server.submissions),1)
    def test_no_output_timeout_does_not_switch(self):
        f=self.setup_worker(0);f.server.no_output_nodes.update(f.worker.state['id_map'].values())
        result=self.run_worker(f);self.assertEqual(result['status'],'timed_out');self.assertEqual(len(f.server.submissions),1)
    def test_policy_can_disable_fallback(self):
        f=self.setup_worker();f.worker.package['master_fallback']['enabled']=False
        # Recompile a disabled policy as a new run, rather than mutate a frozen package.
        from starcanvas_executor import Executor
        p=compile_tasks(f.worker.package,f.root/'disabled-package')['package']
        folder=f.root/'disabled-run';folder.mkdir();w=Executor(f.server,folder,clock=f.clock,sleep=f.clock.sleep);w.prepare(p)
        run_chain(w,execute=True,max_wait=10,poll_interval=1);self.assertEqual(len(f.server.submissions),1)
    def test_service_code_is_specific(self):
        self.assertTrue(service_503({'message':'HTTP 503 service unavailable'}))
        self.assertFalse(service_503({'message':'Upstream model service error'}))
        self.assertFalse(service_503('15030'))
    def test_stable_ratio_drift_blocks_before_third_submission(self):
        f=self.setup_worker(3);original=f.server.call
        def call(name,args):
            result=original(name,args)
            if name=='canvas_prepare_run':
                for node in f.server.nodes.values():
                    for row in node.get('rows',[]):
                        if row.get('params',{}).get('model')=='gpt-image-2.5-wd':row['params']['aspectRatio']='auto'
            return result
        f.server.call=call
        with self.assertRaisesRegex(ValueError,'aspectRatio'):self.run_worker(f)
        self.assertEqual(len(f.server.submissions),2)

if __name__=='__main__':unittest.main()
