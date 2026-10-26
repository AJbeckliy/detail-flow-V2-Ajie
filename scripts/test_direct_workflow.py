"""Current default: approved plan directly to all final pages. No live calls."""
import copy
import unittest
import test_executor as fixtures
from test_fixtures import bind_review_fixture
from starcanvas_adapter import compile_tasks,read,validate,sha
from master_fallback import run_chain


class DirectWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ExecutorTests();self.f.setUp();self.m=self.f.manifest
        self.m['workflow']='detail-flow-direct-v3';self.m.pop('visual_master')
        self.m.pop('execution_profile',None)
        self.m['tasks'][0]['model_id']='gpt-image-2.5-wd'

    def compile(self):
        return compile_tasks(self.m,self.f.root/'direct-package')['package']

    def test_full_batch_needs_no_master_or_master_waiver(self):
        self.m['tasks']=[dict(copy.deepcopy(self.m['tasks'][0]),id=f'screen-{i:02d}') for i in range(1,4)]
        bind_review_fixture(self.m,self.f.root)
        path=self.compile();package=read(path)
        self.assertNotIn('visual_master',package);self.assertNotIn('stage_policy',package)
        self.assertNotIn('master_fallback',package)
        self.f.worker.prepare(path)
        result=run_chain(self.f.worker,execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual(len(self.f.server.submissions),1)
        self.assertEqual(len(self.f.server.submissions[0]),3)
        self.assertFalse((self.f.folder/'fallback-chain.json').exists())

    def test_design_and_current_review_revision_still_required(self):
        for field,pattern in (('design_approval','design approval'),('approved_plan','approved_plan')):
            m=copy.deepcopy(self.m);m.pop(field)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,pattern):validate(m)

    def test_default_does_not_accept_master_images_or_staged_trial_without_authority(self):
        m=copy.deepcopy(self.m);m['tasks'][0]['references'].append({'role':'visual_master','path':str(self.f.root/'master.png')})
        with self.assertRaisesRegex(ValueError,'product references only'):validate(m)
        self.m['ready_stage']='sample'
        with self.assertRaisesRegex(ValueError,'staged sample|staged.*authority|explicit user authority'):validate(self.m)

    def test_master_generation_requires_explicit_request(self):
        self.m['ready_stage']='master';self.m['tasks'][0].update(kind='master',model_id='gpt-image-2.5-wd',resolution='1K',aspect_ratio='9:16')
        with self.assertRaisesRegex(ValueError,'master_request'):validate(self.m)
        self.m['master_request']={'evidence':'Offline fixture: user explicitly requested a visual preview'}
        self.assertTrue(validate(self.m)['ready'])
        package=read(self.compile());self.assertEqual(package['master_request'],self.m['master_request'])

    def test_explicit_master_gate_remains_binding_when_user_requested_it(self):
        self.m['stage_policy']={'master':{'mode':'approved','evidence':'Offline explicit optional preview gate'}}
        with self.assertRaisesRegex(ValueError,'master binding'):validate(self.m)

    def test_recorded_preview_request_cannot_be_dropped_before_final_batch(self):
        self.m['master_request']={'evidence':'Offline user request to see preview first'}
        with self.assertRaisesRegex(ValueError,'master approval'):validate(self.m)
        path=self.f.root/'master.png'
        self.m['visual_master']={'path':str(path),'sha256':sha(path),'approval_evidence':'Offline user accepted requested preview'}
        self.assertTrue(validate(self.m)['ready'])

    def test_old_v2_contract_is_not_silently_reinterpreted(self):
        self.m['workflow']='detail-flow-copy-led-v2'
        with self.assertRaisesRegex(ValueError,'master approval'):validate(self.m)
        self.m['stage_policy']={'master':{'mode':'waived','evidence':'Historical explicit waiver'}}
        self.assertTrue(validate(self.m)['ready'])

    def test_historical_optional_master_keeps_its_bounded_fallback(self):
        self.m['execution_profile']='pt25-stage-sunburst-v3'
        self.m['ready_stage']='master';self.m['tasks'][0].update(kind='master',model_id='gpt-image-2.5-wd',resolution='1K',aspect_ratio='9:16')
        self.m['tasks'][0].update(model_id='gpt-image-2.5-qy',resolution='2K',aspect_ratio='9:21')
        self.m['master_request']={'evidence':'Offline explicit user request for preview with bounded fallback'}
        self.f.worker.prepare(self.compile());original=self.f.server.call
        def call(name,args):
            if name=='canvas_run_node' and not self.f.server.submissions:self.f.server.fail_nodes.update(args['nodeIds'])
            result=original(name,args)
            if name=='task_get' and result['data']['status']=='error':result['data']['error']={'statusCode':503}
            return result
        self.f.server.call=call
        result=run_chain(self.f.worker,execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review');self.assertEqual(len(self.f.server.submissions),2)
        child=read(self.f.folder/'fallback-package-1/package.json')
        self.assertEqual(child['workflow'],'detail-flow-direct-v3')
        self.assertEqual(child['master_request'],self.m['master_request'])


if __name__=='__main__':unittest.main()
