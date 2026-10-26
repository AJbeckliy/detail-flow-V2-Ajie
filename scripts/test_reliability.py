"""Failure-boundary regressions. Fake server and local files; no paid calls."""
import copy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

import master_fallback as fallback
import starcanvas_executor as runtime
from starcanvas_adapter import compile_tasks, read, sha
import test_executor as executor_fixtures
import test_master_fallback as fallback_fixtures
import skill_release
import setup_detail_flow as setup


class RecoveryTests(unittest.TestCase):
    def test_textual_account_failures_never_advance_chain(self):
        messages = (
            'Upstream model service error: rate limit exceeded',
            'Upstream model service error: Too many requests',
            'Upstream model service error: authentication failed',
            '上游模型服务错误：请求被限流，请稍后再试',
        )
        for message in messages:
            with self.subTest(message=message):
                f = fallback_fixtures.MasterFallbackTests().setup_worker(3, message)
                result = fallback.run_chain(f.worker, execute=True, max_wait=10, poll_interval=1)
                self.assertEqual(len(f.server.submissions), 1)
                self.assertEqual(result['status'], 'partial_failure')

    def test_local_collection_can_recover_without_client_or_submission(self):
        f = executor_fixtures.ExecutorTests(); f.setUp(); f.prepare(1)
        with patch.object(runtime, 'reconcile', side_effect=PermissionError('temporary file lock')):
            f.worker.run(execute=True, max_wait=10, poll_interval=1)
        self.assertEqual(f.worker.state['tasks']['screen-01']['status'], 'collection_pending')
        calls = len(f.server.calls)
        recovered = runtime.Executor(None, f.folder).recollect()
        self.assertEqual(recovered['status'], 'complete_needs_review')
        self.assertEqual(len(f.server.calls), calls)
        self.assertEqual(len(f.server.submissions), 1)

    def test_resume_recovers_historical_output_invalid_without_resubmission(self):
        f = executor_fixtures.ExecutorTests(); f.setUp(); f.prepare(1)
        f.worker.run(execute=True, max_wait=10, poll_interval=1)
        f.worker.state['tasks']['screen-01']['status'] = 'output_invalid'
        f.worker.state['status'] = 'partial_failure'; f.worker.save()
        result = runtime.Executor(f.server, f.folder, clock=f.clock, sleep=f.clock.sleep).run(
            resume=True, max_wait=10, poll_interval=1)
        self.assertEqual(result['status'], 'complete_needs_review')
        self.assertEqual(len(f.server.submissions), 1)

    def test_fallback_compile_interruption_resumes_same_attempt(self):
        f = fallback_fixtures.MasterFallbackTests().setup_worker(1)
        original = fallback.compile_tasks
        def interrupted(*args, **kwargs):
            result = original(*args, **kwargs)
            raise OSError('interrupted after durable package creation')
        with patch.object(fallback, 'compile_tasks', side_effect=interrupted):
            with self.assertRaises(OSError):
                fallback.run_chain(f.worker, execute=True, max_wait=10, poll_interval=1)
        self.assertEqual(len(f.server.submissions), 1)
        result = fallback.run_chain(f.worker, resume=True, max_wait=10, poll_interval=1)
        self.assertEqual(result['status'], 'complete_needs_review')
        self.assertEqual(len(f.server.submissions), 2)
        again = fallback.run_chain(f.worker, resume=True, max_wait=10, poll_interval=1)
        self.assertEqual(again['selected_tier'], 1)
        self.assertEqual(len(f.server.submissions), 2)

    def test_status_reports_selected_child_and_retains_root_failure(self):
        f = fallback_fixtures.MasterFallbackTests().setup_worker(1)
        fallback.run_chain(f.worker, execute=True, max_wait=10, poll_interval=1)
        status = runtime.run_status(f.folder)
        self.assertEqual(status['status'], 'complete_needs_review')
        self.assertEqual(status['root_attempt_status'], 'partial_failure')
        self.assertEqual(status['selected_tier'], 1)
        self.assertEqual(read(f.folder/'report.json')['status'], 'complete_needs_review')

    def test_recollection_refuses_another_remote_task(self):
        f=executor_fixtures.ExecutorTests();f.setUp();f.prepare(1)
        f.worker.run(execute=True,max_wait=10,poll_interval=1)
        f.worker.state['tasks']['screen-01']['status']='output_invalid';f.worker.save()
        path=f.folder/'tasks/screen-01.json';remote=read(path);remote['runTargetId']='foreign-workshop'
        path.write_text(json.dumps(remote),encoding='utf-8')
        calls=len(f.server.calls)
        with self.assertRaisesRegex(ValueError,'identity changed'):runtime.Executor(None,f.folder).recollect()
        self.assertEqual(len(f.server.calls),calls);self.assertEqual(len(f.server.submissions),1)

    def test_legacy_orphan_package_can_be_adopted_but_modified_package_cannot(self):
        for tamper in (False,True):
            with self.subTest(tamper=tamper):
                f=fallback_fixtures.MasterFallbackTests().setup_worker(1)
                original=fallback.compile_tasks
                def interrupted(*args,**kwargs):
                    original(*args,**kwargs)
                    raise OSError('crash before next preparation')
                with patch.object(fallback,'compile_tasks',side_effect=interrupted),self.assertRaises(OSError):
                    fallback.run_chain(f.worker,execute=True,max_wait=10,poll_interval=1)
                chain=read(f.folder/'fallback-chain.json');chain['attempts']=chain['attempts'][:1]
                (f.folder/'fallback-chain.json').write_text(json.dumps(chain),encoding='utf-8')
                if tamper:
                    path=f.folder/'fallback-package-1/package.json';package=read(path);package['authority']='different scope'
                    path.write_text(json.dumps(package),encoding='utf-8')
                    with self.assertRaisesRegex(ValueError,'package differs'):
                        fallback.run_chain(f.worker,resume=True,max_wait=10,poll_interval=1)
                    self.assertEqual(len(f.server.submissions),1)
                else:
                    result=fallback.run_chain(f.worker,resume=True,max_wait=10,poll_interval=1)
                    self.assertEqual(result['status'],'complete_needs_review');self.assertEqual(len(f.server.submissions),2)

    def test_previously_authorized_unbound_run_keeps_recovery_contract(self):
        f=executor_fixtures.ExecutorTests();f.setUp()
        package=compile_tasks(f.manifest,f.root/'historical-package',require_review_binding=False)['package']
        f.worker.prepare(package)
        f.server.drop_response=True;f.server.ambiguous=True
        self.assertEqual(f.worker.run(execute=True,max_wait=0)['status'],'submission_unknown')
        f.server.tasks.pop('task-2')
        result=runtime.Executor(f.server,f.folder,clock=f.clock,sleep=f.clock.sleep).run(resume=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review');self.assertEqual(len(f.server.submissions),1)


class ReviewBindingTests(unittest.TestCase):
    def setUp(self):
        f = executor_fixtures.ExecutorTests(); f.setUp(); self.root=f.root; self.m=f.manifest
        self.plan={'pages':[{'slice_id':str(i), 'text_exact':{'headline':f'准确标题{i}'}}
                            for i in range(1,4)]}
        path=self.root/'approved-plan.json'
        path.write_text(json.dumps(self.plan,ensure_ascii=False),encoding='utf-8')
        self.m['approved_plan']={'path':str(path),'sha256':sha(path),
                                 'approval_evidence':'Explicit offline approval fixture'}
        self.m['tasks']=[]
        for page in self.plan['pages']:
            prompt=self.root/('page-'+page['slice_id']+'.txt')
            prompt.write_text('设计指令\n'+page['text_exact']['headline'],encoding='utf-8')
            self.m['tasks'].append(dict(copy.deepcopy(f.manifest['tasks'][0]) if f.manifest['tasks'] else {
                'kind':'slice','model_id':'gpt-image-2.5-1k-qy','resolution':'1K','quality':'auto',
                'aspect_ratio':'9:16','references':[{'role':'product','path':str(self.root/'product.png')}]},
                id='screen-'+page['slice_id'],page_id=page['slice_id'],prompt_path=str(prompt)))

    def test_stale_prompt_rejected_after_review_edit(self):
        Path(self.m['tasks'][0]['prompt_path']).write_text('旧标题',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'copy|文案'):
            compile_tasks(self.m,self.root/'stale')

    def test_production_missing_page_rejected_but_explicit_repair_subset_works(self):
        self.m['tasks']=self.m['tasks'][:1]
        with self.assertRaisesRegex(ValueError,'page|页面'):
            compile_tasks(self.m,self.root/'incomplete')
        self.m['ready_stage']='repair'
        self.m['repair_authorization']={'mode':'explicit','evidence':'Offline authorization for one repair',
                                        'task_ids':[self.m['tasks'][0]['id']],'max_generations':1}
        from test_fixtures import bind_repair_fixture
        bind_repair_fixture(self.m,self.root)
        package=read(compile_tasks(self.m,self.root/'repair')['package'])
        self.assertEqual(len(package['tasks']),1)
        self.assertEqual(package['review_binding_version'],1)

    def test_current_revision_and_full_set_compile_without_rewriting_prompt(self):
        before=Path(self.m['tasks'][0]['prompt_path']).read_bytes().decode('utf-8')
        package=read(compile_tasks(self.m,self.root/'valid')['package'])
        self.assertEqual(package['operations'][1]['data']['prompt'],before)
        self.assertEqual(package['approved_plan'],self.m['approved_plan'])

    def test_foreign_review_receipt_is_rejected(self):
        from prepare_review import prepare_review
        plan=Path(__file__).resolve().parents[1]/'examples/layout-preview.json'
        receipt=prepare_review(plan,self.root/'foreign-review',no_open=True)
        self.m['review_delivery']={'kind':'editable_html','receipt_path':receipt['receipt_path'],
                                  'receipt_sha256':sha(receipt['receipt_path']),'presentation_evidence':'Offline fixture'}
        with self.assertRaisesRegex(ValueError,'delivered review revision'):
            compile_tasks(self.m,self.root/'foreign')

    def test_changed_approved_file_is_rejected_before_compile(self):
        Path(self.m['approved_plan']['path']).write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'revision changed'):
            compile_tasks(self.m,self.root/'changed')

    def test_missing_review_binding_cannot_be_newly_compiled(self):
        self.m.pop('approved_plan')
        with self.assertRaisesRegex(ValueError,'approved_plan'):
            compile_tasks(self.m,self.root/'missing')

    def test_master_can_use_approved_representative_copy_without_all_final_pages(self):
        self.m['ready_stage']='master'
        self.m['tasks']=self.m['tasks'][:1]
        self.m['tasks'][0].update(kind='master',model_id='gpt-image-2.5-qy',resolution='2K',aspect_ratio='9:21',
                                  page_ids=['1'],copy_keys={'1':['headline']})
        self.assertEqual(len(read(compile_tasks(self.m,self.root/'master')['package'])['tasks']),1)

    def test_editable_review_export_revision_compiles_after_actual_adoption_record(self):
        from prepare_review import prepare_review
        source={'title':'Offline lineage fixture','aspect_ratio':'9:16','design_width':720,
                'pages':[{'slice_id':'1','text_exact':{'headline':'初稿'},'layout':{'blocks':[
                    {'id':'title','type':'text','copy_key':'headline','box':[.1,.1,.8,.1],'font_size':32}]}}]}
        path=self.root/'review-source.json';path.write_text(json.dumps(source,ensure_ascii=False),encoding='utf-8')
        receipt=prepare_review(path,self.root/'review',no_open=True)
        source['pages'][0]['text_exact']['headline']='确认改稿'
        source['review_state']={'source_plan_sha256':sha(path),'generation_authorized':False,'prompts_require_recompile':True}
        adopted=self.root/'adopted.json';adopted.write_text(json.dumps(source,ensure_ascii=False),encoding='utf-8')
        self.m['approved_plan']={'path':str(adopted),'sha256':sha(adopted),'approval_evidence':'Explicit offline adoption record'}
        self.m['review_delivery']={'kind':'editable_html','receipt_path':receipt['receipt_path'],
                                  'receipt_sha256':sha(receipt['receipt_path']),'presentation_evidence':'Offline delivered fixture'}
        self.m['tasks']=self.m['tasks'][:1]
        Path(self.m['tasks'][0]['prompt_path']).write_text('准确文案：确认改稿',encoding='utf-8')
        package=read(compile_tasks(self.m,self.root/'adopted-package')['package'])
        self.assertIn('确认改稿',package['operations'][1]['data']['prompt'])


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='detail-release-test-'))
        self.source=self.root/'source';self.source.mkdir()
        (self.source/'SKILL.md').write_text('name: detail-flow-starcanvas',encoding='utf-8')
        (self.source/'scripts').mkdir();(self.source/'scripts/runner.py').write_text('value = 1',encoding='utf-8')

    def seal(self,revision):
        value=dict(version=1,revision=revision,**skill_release.fingerprint(self.source))
        (self.source/'release-manifest.json').write_text(json.dumps(value),encoding='utf-8')
        return value

    def test_installed_release_and_receipt_detect_old_or_modified_content(self):
        first=self.seal('fixture-1');target=self.root/'installed'
        with patch.object(setup,'ROOT',self.source):setup.install_skill(target)
        receipt=self.root/'ready.json'
        receipt.write_text(json.dumps({'status':'ready','skill_path':str(target),'skill_revision':'fixture-1',
                                       'skill_content_sha256':first['content_sha256']}),encoding='utf-8')
        skill_release.verify_receipt(target,receipt)
        (self.source/'scripts/runner.py').write_text('value = 2',encoding='utf-8')
        self.seal('fixture-2')
        with patch.object(setup,'ROOT',self.source):setup.install_skill(target)
        with self.assertRaisesRegex(ValueError,'READY_RELEASE_MISMATCH'):skill_release.verify_receipt(target,receipt)
        (target/'scripts/runner.py').write_text('value = 3',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'RELEASE_CONTENT_MISMATCH'):skill_release.verify(target)

    def test_source_and_published_skill_names_share_fingerprint(self):
        first=skill_release.fingerprint(self.source)
        (self.source/'SKILL.md').write_text('name: detail-flow',encoding='utf-8')
        self.assertEqual(first,skill_release.fingerprint(self.source))

    def test_audit_outputs_and_bytecode_do_not_enter_release(self):
        first=skill_release.fingerprint(self.source)
        (self.source/'outputs').mkdir();(self.source/'outputs/private.json').write_text('{}')
        (self.source/'scripts/__pycache__').mkdir();(self.source/'scripts/__pycache__/runner.pyc').write_bytes(b'fixture')
        self.assertEqual(first,skill_release.fingerprint(self.source))


if __name__=='__main__':unittest.main()
