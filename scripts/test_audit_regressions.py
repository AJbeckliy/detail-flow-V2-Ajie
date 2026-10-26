"""Behavioral regressions from the 2026-10 audit; local synthetic files only."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from PIL import Image, ImageChops
from starcanvas_adapter import compile_tasks, assert_readback, reconcile, read, sha, validate
from render_layout_preview import audit_plan, choose_font, draw_page, render_plan
from build_review_editor import build_editor
from test_fixtures import workshop_fixture,bind_review_fixture

ROOT=Path(__file__).resolve().parents[1]


class AuditRegressions(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='detail-audit-regression-'))
        for name,size,color in [('product.png',(90,160),'blue'),('master.png',(90,270),'green')]:
            Image.new('RGB',size,color).save(self.root/name)
        (self.root/'prompt.txt').write_text('Offline fixture; no execution authority',encoding='utf-8')
        self.m={'version':1,'execution_profile':'pt25-stage-sunburst-v3','workflow':'detail-flow-copy-led-v2','ready_stage':'production','authority':'offline test only','design_approval':'fixture',
                'review_delivery':{'kind':'user_alternative','evidence':'Explicit synthetic test without production'},
                'visual_master':{'path':str(self.root/'master.png'),'sha256':sha(self.root/'master.png'),'approval_evidence':'fixture'},
                'tasks':[{'id':'screen-01','kind':'slice','prompt_path':str(self.root/'prompt.txt'),'model_id':'gpt-image-2.5-1k-qy','resolution':'1K','quality':'auto','aspect_ratio':'9:16','references':[{'role':'product','path':str(self.root/'product.png')}]}]}
        bind_review_fixture(self.m,self.root)

    def package(self):
        p=read(compile_tasks(self.m,self.root/'package')['package'])
        rb={'generators':{'screen-01':copy.deepcopy(p['operations'][1]['data'])},'references':{'screen-01':[str(self.root/'product.png')]}}
        rb['generators']['screen-01'].pop('title',None)
        rb['workshops']={'screen-01':workshop_fixture(p['tasks'][0])}
        return p,rb

    def test_quality_change_and_missing_readback_fail(self):
        p,rb=self.package()
        for value in ('low',None):
            rb['generators']['screen-01']['quality']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'quality'):assert_readback(p,rb)

    def test_quality_auto_is_compared(self):
        self.m['tasks'][0].pop('quality');p,rb=self.package()
        self.assertEqual(assert_readback(p,rb)['readback'],'exact_match')
        rb['generators']['screen-01']['quality']='high'
        with self.assertRaises(ValueError):assert_readback(p,rb)

    def test_relative_cli_paths_independent_of_cwd_and_readback_location(self):
        m=copy.deepcopy(self.m)
        m['tasks'][0]['prompt_path']='prompt.txt';m['tasks'][0]['references'][0]['path']='product.png';m['visual_master']['path']='master.png'
        m['frozen_planning']=[{'path':'prompt.txt','sha256':sha(self.root/'prompt.txt')}]
        f=self.root/'ready.json';f.write_text(json.dumps(m),encoding='utf-8')
        for i,cwd in enumerate((self.root,ROOT)):
            proc=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/starcanvas_adapter.py'),'compile',str(f),str(self.root/f'pkg-{i}')],cwd=cwd,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            p=read(self.root/f'pkg-{i}/package.json');t=p['tasks'][0]
            for value in (t['prompt_path'],t['references'][0]['path'],p['visual_master']['path'],p['frozen_planning'][0]['path']):self.assertTrue(Path(value).is_absolute())
            self.assertEqual(assert_readback(p,{'generators':{'screen-01':p['operations'][1]['data']},'references':{'screen-01':[str(self.root/'product.png')]},'workshops':{'screen-01':workshop_fixture(t)}})['readback'],'exact_match')

    def returns(self,count=2):
        p,rb=self.package();folder=Path(p['tasks'][0]['output_dir']);folder.mkdir();rows=[]
        now=time.time()*1000
        for i in range(count):
            file=folder/f'candidate-{i}.png';Image.new('RGB',(90,160),(i,0,0)).save(file)
            rows.append({'source':'generated','nodeId':'workshop','taskId':'remote','path':str(file)})
        state={'readbacks':rb,'id_map':{'screen-01-workshop':'workshop'},'runs':[{'nodeId':'workshop','taskId':'remote'}]}
        snapshot={'remote':{'id':'remote','status':'done','startedAt':now,'endedAt':time.time()*1000,'outputs':{'generated':rows+rows[:1]}}}
        return p,state,snapshot,rows

    def test_multiple_candidates_require_selection_and_preserve_originals(self):
        p,state,snapshot,rows=self.returns();before={r['path']:sha(r['path']) for r in rows}
        result=reconcile(p,state,snapshot,self.root/'return')
        self.assertEqual(len(result['candidates']),2);self.assertEqual(result['images'],[]);self.assertEqual(result['selection_required'],['screen-01'])
        selected=result['candidates'][1]
        state['selected_candidates']={'screen-01':{'path':selected['path'],'sha256':selected['sha256'],'evidence':'fixture internal choice'}}
        result=reconcile(p,state,snapshot,self.root/'selected')
        self.assertEqual(result['images'][0]['path'],selected['path']);self.assertFalse(result['selection_required'])
        self.assertEqual(before,{r['path']:sha(r['path']) for r in rows})
        self.assertEqual(result['visual_status'],'needs_agent_review')

    def test_invalid_selection_and_bad_candidate_are_rejected(self):
        p,state,snapshot,rows=self.returns()
        state['selected_candidates']={'screen-01':{'path':str(self.root/'product.png'),'sha256':sha(self.root/'product.png'),'evidence':'fixture'}}
        with self.assertRaisesRegex(ValueError,'Selected candidate'):reconcile(p,state,snapshot,self.root/'bad-selection')
        state.pop('selected_candidates');Image.new('RGB',(100,100)).save(rows[1]['path'])
        result=reconcile(p,state,snapshot,self.root/'bad-ratio')
        self.assertEqual(len(result['images']),1)
        self.assertEqual(result['rejected_candidates'][0]['reason'],'ratio_mismatch')

    def test_input_echo_excluded_even_when_ratio_matches(self):
        p,state,snapshot,rows=self.returns()
        shutil.copyfile(self.root/'product.png',rows[0]['path'])
        result=reconcile(p,state,snapshot,self.root/'echo-mixed')
        self.assertEqual(len(result['echoes']),1)
        self.assertTrue(result['echoes'][0]['input_echo'])
        self.assertEqual(len(result['candidates']),1)
        self.assertEqual(result['images'][0]['path'],rows[1]['path'])
        self.assertFalse(result['selection_required'])
        self.assertEqual(Path(rows[0]['path']).read_bytes(),(self.root/'product.png').read_bytes())

    def test_wrong_ratio_input_echo_does_not_block_valid_output(self):
        Image.new('RGB',(375,500),'blue').save(self.root/'product.png')
        p,state,snapshot,rows=self.returns()
        shutil.copyfile(self.root/'product.png',rows[0]['path'])
        result=reconcile(p,state,snapshot,self.root/'echo-wrong-ratio')
        self.assertEqual(len(result['echoes']),1);self.assertEqual(len(result['images']),1)

    def test_all_echoes_fail_without_deliverable_or_deleting_files(self):
        p,state,snapshot,rows=self.returns()
        for row in rows:shutil.copyfile(self.root/'product.png',row['path'])
        with self.assertRaisesRegex(ValueError,'all returned files are input echoes'):
            reconcile(p,state,snapshot,self.root/'all-echo')
        self.assertFalse((self.root/'all-echo').exists())
        self.assertTrue(all(Path(row['path']).is_file() for row in rows))

    def test_echo_cannot_be_selected_as_final(self):
        p,state,snapshot,rows=self.returns()
        shutil.copyfile(self.root/'product.png',rows[0]['path'])
        state['selected_candidates']={'screen-01':{'path':rows[0]['path'],'sha256':sha(rows[0]['path']),'evidence':'fixture mistaken selection'}}
        with self.assertRaisesRegex(ValueError,'Selected candidate is not a verified result'):
            reconcile(p,state,snapshot,self.root/'echo-selection')

    def test_missing_workflow_needs_explicit_experiment(self):
        self.m.pop('workflow')
        with self.assertRaisesRegex(ValueError,'legacy_experiment'):validate(self.m)
        self.m['legacy_experiment']={'evidence':'explicit offline deviation'}
        self.assertTrue(validate(self.m)['ready'])
        p,rb=self.package();self.assertEqual(assert_readback(p,rb)['readback'],'exact_match')
        p.pop('legacy_experiment') # historical package reading still works
        self.assertEqual(assert_readback(p,rb)['readback'],'exact_match')

    def test_design_delegation_retains_master_binding(self):
        self.m.pop('design_approval');self.m['stage_policy']={'design':{'mode':'delegated','evidence':'fixture explicit delegation plus internal review'}}
        p,rb=self.package();self.assertEqual(p['stage_policy'],self.m['stage_policy']);assert_readback(p,rb)
        self.m.pop('visual_master')
        with self.assertRaises(ValueError):validate(self.m)

    def test_explicit_master_waiver_keeps_product_only_and_optional_staged_gates(self):
        self.m.pop('visual_master');self.m['stage_policy']={'master':{'mode':'waived','evidence':'fixture explicit master waiver'}}
        self.assertTrue(validate(self.m)['ready'])
        bad=copy.deepcopy(self.m);bad['tasks'][0]['references'][0]['role']='style'
        with self.assertRaises(ValueError):validate(bad)
        self.m['ready_stage']='remaining'
        self.m['staged_review_authority']='fixture explicitly requested staged review'
        with self.assertRaises(ValueError):validate(self.m)
        self.m['sample_review']='fixture internal vertical review'
        p,rb=self.package();self.assertEqual(assert_readback(p,rb)['readback'],'exact_match')

    def test_stage_exceptions_need_evidence_and_validate_supplied_master(self):
        for value in ({'mode':'waived','evidence':''},{'mode':'guess','evidence':'x'},True):
            self.m['stage_policy']={'master':value}
            with self.subTest(value=value),self.assertRaises(ValueError):validate(self.m)
        self.m['stage_policy']={'master':{'mode':'waived','evidence':'fixture'}}
        self.m['visual_master']['sha256']='0'*64
        with self.assertRaises(ValueError):validate(self.m)

    def plan(self):
        return {'aspect_ratio':'1:1','pages':[{'slice_id':'01','text_exact':{'title':'AB'},'layout':{'blocks':[{'id':'title','type':'text','copy_key':'title','box':[.1,.1,.8,.2],'font_size':32,'align':'left','color':'red'}]}}]}

    def test_alignment_changes_actual_pixels_and_invalid_align_rejected(self):
        plan=self.plan();images=[]
        for align in ('left','center','right'):
            plan['pages'][0]['layout']['blocks'][0]['align']=align
            pages,issues=audit_plan(plan,self.root,720,choose_font());self.assertFalse(issues);images.append(draw_page(pages[0],choose_font()))
        self.assertIsNotNone(ImageChops.difference(images[0],images[2]).getbbox())
        self.assertIsNotNone(ImageChops.difference(images[1],images[2]).getbbox())
        plan['pages'][0]['layout']['blocks'][0]['align']='sideways'
        self.assertIn('ALIGN',{x['code'] for x in audit_plan(plan,self.root,720,choose_font())[1]})

    @unittest.skipUnless(shutil.which('node'),'Node required for cross-language handoff test')
    def test_js_deletion_and_named_color_editor_roundtrip_to_python(self):
        plan=self.plan();source=self.root/'plan.json';source.write_text(json.dumps(plan),encoding='utf-8')
        html=build_editor(source,self.root/'review.html')
        payload=json.loads(html.read_text(encoding='utf-8').split('<script id="data" type="application/json">')[1].split('</script>')[0])
        self.assertEqual(payload['plan']['pages'][0]['layout']['blocks'][0]['color'],'#ff0000')
        self.assertEqual(read(source),plan)
        out=self.root/'js-exports'
        proc=subprocess.run(['node',str(ROOT/'scripts/test_editor_handoff.cjs'),str(out),str(html)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(render_plan(out/'deleted.json',self.root/'deleted-render')['status'],'layout_ready_for_review')
        empty=render_plan(out/'empty.json',self.root/'empty-render')
        self.assertEqual(empty['status'],'layout_needs_revision');self.assertIn('EMPTY_PAGE',{x['code'] for x in empty['issues']})
        self.assertEqual(len(read(out/'empty.json')['pages']),1)


if __name__=='__main__':unittest.main()
