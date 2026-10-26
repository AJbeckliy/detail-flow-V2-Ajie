"""Local transport checks; approval strings are fixtures, not execution authority."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from starcanvas_adapter import validate, compile_tasks, assert_readback, sha
from test_fixtures import workshop_fixture,bind_review_fixture


class CopyLedTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='copy-led-'))
        self.m = json.loads((Path(__file__).resolve().parents[1] / 'examples/copy-led-workflow.json').read_text(encoding='utf-8'))['production_manifest']
        # Retain coverage of the historical v2 approval contract after v3 becomes default.
        self.m['workflow']='detail-flow-copy-led-v2'
        self.m['execution_profile']='pt25-stage-sunburst-v3'
        self.m['tasks'][0]['model_id']='gpt-image-2.5-1k-qy'
        self.m['visual_master']={'approval_evidence':'Historical offline confirmed-master fixture'}
        self.m['review_delivery']={'kind':'user_alternative','evidence':'Explicit offline fixture: no user-facing image production'}
        for name in ('product.jpg', 'master-confirmed.png', 'screen-01.txt'):
            (self.root / name).write_bytes(('fixture ' + name).encode())
        t = self.m['tasks'][0]
        t['prompt_path'] = str(self.root / 'screen-01.txt')
        t['references'] = [{'role':'product', 'path':str(self.root / 'product.jpg')}]
        self.m['visual_master'].update(path=str(self.root / 'master-confirmed.png'), sha256=sha(self.root / 'master-confirmed.png'))
        bind_review_fixture(self.m,self.root)

    def test_product_only_compile_preserves_evidence_without_attaching_master(self):
        result = compile_tasks(self.m, self.root / 'package')
        package = json.loads(Path(result['package']).read_text(encoding='utf-8'))
        self.assertEqual(package['workflow'], 'detail-flow-copy-led-v2')
        self.assertEqual(package['visual_master'], self.m['visual_master'])
        t = package['tasks'][0]
        self.assertEqual(len(t['references']), 1)
        rb = {'generators':{t['id']:package['operations'][1]['data']}, 'references':{t['id']:[str(self.root/'product.jpg')]}}
        rb['workshops']={t['id']:workshop_fixture(t)}
        self.assertEqual(assert_readback(package, rb)['readback'], 'exact_match')
        rb['references'][t['id']].append(str(self.root/'master-confirmed.png'))
        with self.assertRaises(ValueError): assert_readback(package, rb)

    def test_master_style_sketch_refs_rejected(self):
        for role in ('visual_master', 'style', 'sketch'):
            m = copy.deepcopy(self.m)
            m['tasks'][0]['references'].append({'role':role, 'path':str(self.root/'master-confirmed.png')})
            with self.subTest(role=role), self.assertRaises(ValueError): validate(m)

    def test_master_disguised_as_product_rejected_by_hash(self):
        shutil.copy2(self.root/'master-confirmed.png', self.root/'disguised.jpg')
        self.m['tasks'][0]['references'].append({'role':'product','path':str(self.root/'disguised.jpg')})
        with self.assertRaisesRegex(ValueError, 'disguised'): validate(self.m)

    def test_multiple_real_product_views_allowed(self):
        (self.root/'detail.jpg').write_bytes(b'distinct product detail')
        self.m['tasks'][0]['references'].append({'role':'product','path':str(self.root/'detail.jpg')})
        self.assertTrue(validate(self.m)['ready'])

    def test_approvals_retained_and_staged_review_only_with_explicit_authority(self):
        m = copy.deepcopy(self.m); m.pop('design_approval')
        with self.assertRaises(ValueError): validate(m)
        m = copy.deepcopy(self.m); m.pop('visual_master')
        with self.assertRaises(ValueError): validate(m)
        self.m['ready_stage']='sample'
        with self.assertRaisesRegex(ValueError,'explicit user authority'):validate(self.m)
        self.m['staged_review_authority']='fixture user explicitly requests first-two trial'
        self.assertTrue(validate(self.m)['ready'])
        for i in range(2):
            t = copy.deepcopy(self.m['tasks'][0]); t['id'] = f'page-extra-{i}'; self.m['tasks'].append(t)
        with self.assertRaises(ValueError): validate(self.m)
        self.m['ready_stage'] = 'remaining'
        with self.assertRaises(ValueError): validate(self.m)
        self.m['sample_review'] = 'fixture reviewed first two pages as a set'
        bind_review_fixture(self.m,self.root)
        self.assertTrue(validate(self.m)['ready'])

    def test_master_stage_can_still_use_style_references(self):
        self.m['ready_stage'] = 'master'; self.m.pop('visual_master')
        t = self.m['tasks'][0]; t.update(kind='master', aspect_ratio='9:21', model_id='gpt-image-2.5-qy', resolution='2K')
        t['references'].append({'role':'style','path':str(self.root/'master-confirmed.png')})
        self.assertTrue(validate(self.m)['ready'])

    def test_optional_remaining_batches_still_work_when_requested(self):
        for total in (8,10,12):
            m=copy.deepcopy(self.m);m['ready_stage']='remaining';m['sample_review']='fixture first-two internal review completed'
            m['staged_review_authority']='fixture explicit staged trial'
            m['tasks']=[dict(copy.deepcopy(self.m['tasks'][0]),id=f'screen-{i:02d}') for i in range(3,total+1)]
            bind_review_fixture(m,self.root)
            result=compile_tasks(m,self.root/f'batch-{total}')
            package=json.loads(Path(result['package']).read_text(encoding='utf-8'))
            self.assertEqual(len(package['tasks']),total-2)
            self.assertTrue(all(not t.get('wait_for') for t in package['tasks']))
            self.assertEqual(len({t['workshop_ref'] for t in package['tasks']}),total-2)
            self.assertFalse(package['paid_submission'])

    def test_whole_eight_ten_twelve_page_sets_need_no_sample_review(self):
        for total in (8,10,12):
            m=copy.deepcopy(self.m)
            m['tasks']=[dict(copy.deepcopy(self.m['tasks'][0]),id=f'screen-{i:02d}') for i in range(1,total+1)]
            bind_review_fixture(m,self.root)
            result=compile_tasks(m,self.root/f'whole-{total}')
            package=json.loads(Path(result['package']).read_text(encoding='utf-8'))
            self.assertEqual(package['ready_stage'],'production')
            self.assertEqual(len(package['tasks']),total)
            self.assertEqual(len({t['workshop_ref'] for t in package['tasks']}),total)
            self.assertEqual(len({t['load_ref'] for t in package['tasks']}),total)
            self.assertEqual(len(package['reference_attachments']),total)
            self.assertNotIn('sample_review',package)
            self.assertTrue(all(not t.get('wait_for') for t in package['tasks']))
            self.assertFalse(package['paid_submission'])

    def test_full_production_still_rejects_mixed_master_and_slice(self):
        master=copy.deepcopy(self.m['tasks'][0])
        master.update(id='master',kind='master',model_id='gpt-image-2.5-qy',resolution='2K',aspect_ratio='9:21')
        self.m['tasks'].append(master)
        with self.assertRaisesRegex(ValueError,'Do not mix'):validate(self.m)


if __name__ == '__main__': unittest.main()
