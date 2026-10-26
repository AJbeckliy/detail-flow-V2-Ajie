"""Mixed candidate recovery and separately scoped repair permission; offline only."""
import copy
import unittest
from pathlib import Path
from PIL import Image
import test_audit_regressions as fixtures
import test_executor as execution
from starcanvas_adapter import compile_tasks,reconcile,read,sha
from starcanvas_executor import Executor
import test_master_fallback as master_fixtures
from master_fallback import run_chain


class CandidateRepairTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.AuditRegressions();self.f.setUp()
        self.p,self.s,self.snap,self.rows=self.f.returns(3)
        Image.new('RGB',(160,160),'purple').save(self.rows[1]['path'])

    def test_mixed_ratios_keep_good_candidates_and_preserve_rejection(self):
        result=reconcile(self.p,self.s,self.snap,self.f.root/'mixed')
        self.assertEqual(len(result['candidates']),2)
        self.assertEqual(result['selection_required'],['screen-01'])
        self.assertEqual(result['rejected_candidates'][0]['reason'],'ratio_mismatch')
        self.assertTrue(Path(self.rows[1]['path']).is_file())

    def test_good_selection_succeeds_and_bad_selection_is_rejected(self):
        for index in (2,1):
            choice={'path':self.rows[index]['path'],'sha256':sha(self.rows[index]['path']),'evidence':'Offline review fixture'}
            state=dict(self.s,selected_candidates={'screen-01':choice})
            if index==1:
                with self.assertRaisesRegex(ValueError,'Selected candidate'):
                    reconcile(self.p,state,self.snap,self.f.root/'bad-choice')
            else:
                result=reconcile(self.p,state,self.snap,self.f.root/'good-choice')
                self.assertEqual(result['images'][0]['sha256'],choice['sha256'])

    def test_corrupt_candidate_does_not_hide_good_images(self):
        Path(self.rows[1]['path']).write_bytes(b'not a decodable image')
        result=reconcile(self.p,self.s,self.snap,self.f.root/'corrupt')
        self.assertEqual(len(result['candidates']),2)
        self.assertEqual(result['rejected_candidates'][0]['reason'],'decode_error')

    def test_all_invalid_fail_with_diagnostic_evidence(self):
        for row in self.rows:Image.new('RGB',(160,160),'purple').save(row['path'])
        dest=self.f.root/'all-invalid'
        with self.assertRaisesRegex(ValueError,'No valid generated candidate'):
            reconcile(self.p,self.s,self.snap,dest)
        report=read(dest/'candidate-audit.json')
        self.assertEqual(len(report['rejected_candidates']),3)

    def test_foreign_identity_still_fails_the_whole_binding(self):
        self.snap['remote']['outputs']['generated'][1]['nodeId']='foreign-node'
        with self.assertRaisesRegex(ValueError,'another workshop'):
            reconcile(self.p,self.s,self.snap,self.f.root/'foreign')

    def test_recollect_then_select_closes_state_without_new_submission(self):
        f=execution.ExecutorTests();f.setUp();f.prepare(1)
        f.worker.run(execute=True,max_wait=10,poll_interval=1)
        task=f.worker.state['tasks']['screen-01'];remote=read(f.folder/'tasks/screen-01.json')
        original=Path(remote['outputs']['generated'][0]['path'])
        square=original.with_name('square.png');Image.new('RGB',(160,160),'purple').save(square)
        other=original.with_name('other.png');Image.new('RGB',(90,160),'orange').save(other)
        for path in (square,other):remote['outputs']['generated'].append(dict(remote['outputs']['generated'][0],path=str(path)))
        from starcanvas_executor import atomic_json
        atomic_json(f.folder/'tasks/screen-01.json',remote)
        task['status']='output_invalid';f.worker.state['status']='partial_failure';f.worker.save()
        local=Executor(None,f.folder)
        self.assertEqual(local.recollect()['status'],'selection_required')
        result=local.select_candidates({'screen-01':{'path':str(other),'sha256':sha(other),'evidence':'Offline chosen candidate'}})
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual(len(f.server.submissions),1)


class RepairAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.f=execution.ExecutorTests();self.f.setUp();self.m=self.f.manifest
        self.m['ready_stage']='repair'

    def grant(self,**changes):
        from test_fixtures import bind_repair_fixture
        bind_repair_fixture(self.m,self.f.root)
        self.m['repair_authorization']=dict(mode='explicit',evidence='Offline user approval: one additional generation for screen-01',
                                            task_ids=['screen-01'],max_generations=1,**changes)

    def test_initial_approval_alone_cannot_compile_paid_repair(self):
        with self.assertRaisesRegex(ValueError,'repair_authorization'):
            compile_tasks(self.m,self.f.root/'no-grant')

    def test_explicit_page_scope_is_frozen_in_package(self):
        self.grant();p=read(compile_tasks(self.m,self.f.root/'grant')['package'])
        self.assertEqual(p['repair_authorization_version'],1)
        self.assertEqual(p['repair_authorization']['task_ids'],['screen-01'])

    def test_wrong_scope_and_missing_or_boolean_budget_rejected(self):
        self.grant()
        for changes in ({'task_ids':['screen-02']},{'max_generations':0},{'max_generations':True},{'evidence':''}):
            m=copy.deepcopy(self.m);m['repair_authorization'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):compile_tasks(m,self.f.root/'bad')

    def test_preapproved_allowance_arithmetic_is_checked(self):
        self.grant();g=self.m['repair_authorization'];g.update(mode='prior_allowance',allowance_total=2,used_generations=2)
        with self.assertRaisesRegex(ValueError,'remaining'):
            compile_tasks(self.m,self.f.root/'exhausted')
        g['used_generations']=1
        self.assertEqual(read(compile_tasks(self.m,self.f.root/'remaining')['package'])['repair_authorization']['max_generations'],1)

    def test_historical_repair_package_cannot_submit_new_generation(self):
        self.m['ready_stage']='production'
        path=Path(compile_tasks(self.m,self.f.root/'historical')['package'])
        package=read(path);package['ready_stage']='repair'
        from starcanvas_executor import atomic_json
        atomic_json(path,package)
        with self.assertRaisesRegex(ValueError,'original-canvas binding'):self.f.worker.prepare(path)
        self.assertEqual(len(self.f.server.submissions),0)

    def test_optional_master_repair_fallback_respects_repair_limit(self):
        for limit in (1,2):
            with self.subTest(limit=limit):
                f=master_fixtures.MasterFallbackTests().setup_worker(3)
                m=copy.deepcopy(f.manifest);m['ready_stage']='repair'
                m['repair_context']={'source_run':str(f.folder),'issues':{m['tasks'][0]['id']:'Offline preview repair'}}
                m['repair_authorization']={'mode':'explicit','evidence':'Offline bounded preview repair approval',
                    'task_ids':[m['tasks'][0]['id']],'max_generations':limit}
                path=compile_tasks(m,f.root/'repair-package')['package']
                folder=f.root/'repair-run';folder.mkdir();worker=Executor(f.server,folder,clock=f.clock,sleep=f.clock.sleep)
                worker.prepare(path);run_chain(worker,execute=True,max_wait=10,poll_interval=1)
                self.assertEqual(len(f.server.submissions),limit)
                run_chain(worker,resume=True,max_wait=10,poll_interval=1)
                self.assertEqual(len(f.server.submissions),limit)


if __name__=='__main__':unittest.main()
