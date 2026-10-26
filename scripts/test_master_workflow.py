"""Synthetic local checks; evidence strings do not establish actual user approval."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from starcanvas_adapter import validate, compile_tasks, assert_readback, sha


class MasterWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='detail-master-test-'))
        example=json.loads((Path(__file__).resolve().parents[1]/'examples/visual-master-workflow.json').read_text(encoding='utf-8'))
        self.manifest=copy.deepcopy(example['sample_manifest'])
        self.manifest['legacy_experiment']={'evidence':'explicit offline historical master contract test'}
        for name in ['product.jpg','master-confirmed.png','screen-01.txt']:
            (self.root/name).write_bytes(('synthetic fixture '+name+'\r\n原样文案').encode('utf-8'))
        t=self.manifest['tasks'][0];t['prompt_path']=str(self.root/'screen-01.txt')
        for ref in t['references']:ref['path']=str(self.root/Path(ref['path']).name)
        self.manifest['visual_master'].update(path=str(self.root/'master-confirmed.png'),sha256=sha(self.root/'master-confirmed.png'))

    def test_confirmed_master_binding_survives_compile_and_readback(self):
        p=compile_tasks(self.manifest,self.root/'package')
        package=json.loads(Path(p['package']).read_text(encoding='utf-8'))
        self.assertEqual(package['visual_master'],self.manifest['visual_master'])
        self.assertFalse(package['paid_submission'])
        task=package['tasks'][0]
        rb={'generators':{task['id']:package['operations'][1]['data']},'references':{task['id']:[r['path'] for r in task['references']]}}
        self.assertEqual(assert_readback(package,rb)['readback'],'exact_match')
        (self.root/'master-confirmed.png').write_bytes(b'replaced master')
        with self.assertRaisesRegex(ValueError,'master changed'):assert_readback(package,rb)

    def test_missing_design_evidence_or_boolean_is_rejected(self):
        for value in [None,True,'  ']:
            self.manifest['design_approval']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate(self.manifest)

    def test_master_generation_needs_plan_but_not_final_master_approval(self):
        m=copy.deepcopy(self.manifest);m.pop('visual_master');m['ready_stage']='master'
        t=m['tasks'][0];t.update(kind='master',aspect_ratio='1:3');t['references']=t['references'][:1]
        self.assertTrue(validate(m)['ready'])
        t['aspect_ratio']='9:16'
        with self.assertRaises(ValueError):validate(m)

    def test_final_pages_require_master_evidence_and_real_binding(self):
        for field in ['approval_evidence','path','sha256']:
            m=copy.deepcopy(self.manifest);m['visual_master'].pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):validate(m)
        m=copy.deepcopy(self.manifest);m.pop('visual_master')
        with self.assertRaises(ValueError):validate(m)

    def test_different_or_duplicate_master_reference_rejected(self):
        t=self.manifest['tasks'][0];t['references'][1]['path']=str(self.root/'product.jpg')
        with self.assertRaises(ValueError):validate(self.manifest)
        t['references'][1]['path']=self.manifest['visual_master']['path']
        t['references'].append(copy.deepcopy(t['references'][1]))
        with self.assertRaises(ValueError):validate(self.manifest)

    def test_sample_batch_limit_and_remaining_internal_review(self):
        for i in [2,3]:
            t=copy.deepcopy(self.manifest['tasks'][0]);t['id']=f'screen-0{i}';self.manifest['tasks'].append(t)
        with self.assertRaises(ValueError):validate(self.manifest)
        self.manifest['ready_stage']='remaining'
        with self.assertRaises(ValueError):validate(self.manifest)
        self.manifest['sample_review']='fixture internal vertical audit, not a third user approval'
        self.assertTrue(validate(self.manifest)['ready'])

    def test_master_and_dependent_pages_cannot_share_batch(self):
        t=copy.deepcopy(self.manifest['tasks'][0]);t.update(id='master',kind='master',aspect_ratio='1:3');self.manifest['tasks'].append(t)
        with self.assertRaises(ValueError):validate(self.manifest)

    def test_product_authority_must_remain_first(self):
        self.manifest['tasks'][0]['references'].reverse()
        with self.assertRaises(ValueError):validate(self.manifest)

    def test_unknown_workflow_rejected(self):
        self.manifest['workflow']='typo'
        with self.assertRaises(ValueError):validate(self.manifest)


if __name__=='__main__':unittest.main()
