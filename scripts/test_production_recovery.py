"""Regressions for observed native return shapes and CR/LF trimming. No MCP calls."""
import copy
import hashlib
from pathlib import Path
import unittest
import test_audit_regressions as fixtures
from starcanvas_adapter import reconcile,compile_tasks,assert_readback,transport_prompt
from starcanvas_executor import verify_package
from test_fixtures import bind_review_fixture

class ProductionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AuditRegressions();self.fixture.setUp();self.root=self.fixture.root

    def native(self):
        p,s,snap,rows=self.fixture.returns(1)
        remote=snap['remote'];remote['runTargetId']='workshop'
        remote['outputs'].update(nodeId='workshop',frozen=True)
        for row in remote['outputs']['generated']:row.pop('nodeId',None)
        return p,s,snap

    def test_frozen_parent_output_identity_collects_and_deduplicates(self):
        p,s,snap=self.native();before=copy.deepcopy(snap)
        result=reconcile(p,s,snap,self.root/'return')
        self.assertEqual(len(result['images']),1);self.assertEqual(snap,before)

    def test_missing_or_conflicting_identity_never_inferred_from_expected(self):
        p,s,snap=self.native()
        for key,value in [('parent','wrong'),('target','wrong'),('frozen',False),('parent',None),('child','wrong')]:
            candidate=copy.deepcopy(snap);r=candidate['remote']
            if key=='parent':r['outputs']['nodeId']=value
            elif key=='target':r['runTargetId']=value
            elif key=='frozen':r['outputs']['frozen']=value
            else:r['outputs']['generated'][0]['nodeId']=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):reconcile(p,s,candidate,self.root/'bad')

    def test_parent_schema_still_rejects_input_echo(self):
        p,s,snap=self.native();path=Path(snap['remote']['outputs']['generated'][0]['path'])
        path.write_bytes((self.root/'product.png').read_bytes())
        with self.assertRaisesRegex(ValueError,'input echoes'):reconcile(p,s,snap,self.root/'echo')

    def test_compile_normalizes_only_terminal_crlf_and_keeps_original_hash(self):
        source=self.root/'prompt.txt';original='  保留「准确文案」\r\n内部换行与空格  \r\n\r\n'.encode('utf8');source.write_bytes(original)
        bind_review_fixture(self.fixture.m,self.root)
        result=compile_tasks(self.fixture.m,self.root/'compiled')
        import json
        package=json.loads(Path(result['package']).read_text(encoding='utf8'));task=package['tasks'][0]
        expected=original.decode('utf8').rstrip('\r\n')
        self.assertEqual(transport_prompt(task),expected);self.assertEqual(source.read_bytes(),original)
        self.assertEqual(task['prompt_sha256'],hashlib.sha256(original).hexdigest())
        self.assertEqual(task['transport_prompt_sha256'],hashlib.sha256(expected.encode()).hexdigest())
        verify_package(package)
        rb={'generators':{task['id']:package['operations'][1]['data']},'references':{task['id']:[r['path'] for r in task['references']]},
            'workshops':{task['id']:{'autoSaveEnabled':True,'rows':[{'params':task['workshop_settings'],'prompt':expected,
                'images':[r['path'] for r in task['references']],'saveDir':task['output_dir'],'saveFilled':True}]}}}
        self.assertEqual(assert_readback(package,rb)['readback'],'exact_match')
        for wrong in (expected.replace('准确','错误'),expected.replace('\r\n','\n'),expected.lstrip(),expected.rstrip(' ')):
            changed=copy.deepcopy(rb);changed['workshops'][task['id']]['rows'][0]['prompt']=wrong
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):assert_readback(package,changed)
        source.write_bytes(original+b'\n')
        with self.assertRaises(ValueError):verify_package(package)

if __name__=='__main__':unittest.main()
