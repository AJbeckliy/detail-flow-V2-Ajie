"""Offline failures that previously triggered repeated production probes."""
import copy
import json
from pathlib import Path
import shutil
import unittest
import test_audit_regressions as audit
from starcanvas_adapter import assert_readback, compile_tasks, extract_readback, readback_export, validate


class ExecutionProfileTests(unittest.TestCase):
    def setUp(self):
        self.fixture=audit.AuditRegressions();self.fixture.setUp()
        self.root=self.fixture.root;self.m=self.fixture.m

    def package(self):
        return self.fixture.package()

    def snapshot(self,package,readback):
        t=package['tasks'][0];sid=t['id']
        mapping={t['load_ref']:'loader',t['gen_ref']:'generator',t['workshop_ref']:'workshop'}
        snapshot={'canvas':{'nodes':[
            {'id':'loader','type':'image/load-image-grid','images':[{'path':p} for p in readback['references'][sid]]},
            dict(readback['generators'][sid],id='generator',type='ai-image/gpt-image'),
            dict(readback['workshops'][sid],id='workshop',type='image/workshop'),
        ]}}
        return snapshot,mapping

    def test_only_fixed_production_model_resolution_quality_compile(self):
        for field,value in [('model_id','gpt-image-2.5-1k-sunburst-qy'),('model_id','gpt-image-2-4k-qy'),('resolution','4K'),('quality','high')]:
            m=copy.deepcopy(self.m);m['tasks'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'Fixed production profile'):validate(m)
        self.assertTrue(validate(self.m)['ready'])

    def test_generator_correct_but_workshop_shadowed_is_rejected(self):
        p,rb=self.package()
        params=rb['workshops']['screen-01']['rows'][0]['params']
        params.update(model='gpt-image-2-4k-qy',gptStyle='none')
        with self.assertRaises(ValueError) as caught:assert_readback(p,rb)
        self.assertIn('effective model',str(caught.exception));self.assertIn('effective gptStyle',str(caught.exception))

    def test_missing_workshop_or_extra_row_is_not_exact_match(self):
        p,rb=self.package()
        missing=copy.deepcopy(rb);missing.pop('workshops')
        with self.assertRaisesRegex(ValueError,'missing actual workshop'):assert_readback(p,missing)
        rb['workshops']['screen-01']['rows']*=2
        with self.assertRaisesRegex(ValueError,'exactly one'):assert_readback(p,rb)

    def test_effective_ratio_quality_transparency_and_save_checked(self):
        p,rb=self.package()
        for key,value in [('aspectRatio','1:1'),('quality','high'),('resolution','4K'),('transparent',True),('gptStyle',None)]:
            bad=copy.deepcopy(rb);bad['workshops']['screen-01']['rows'][0]['params'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):assert_readback(p,bad)
        bad=copy.deepcopy(rb);bad['workshops']['screen-01']['rows'][0]['saveDir']=str(self.root/'previous-attempt')
        with self.assertRaisesRegex(ValueError,'saveDir'):assert_readback(p,bad)

    def test_effective_prompt_and_images_cannot_silently_change(self):
        p,rb=self.package()
        for field,value in [('prompt','old template copy'),('images',[str(self.root/'master.png')]),('images',[str(self.root/'product.png')]*2)]:
            bad=copy.deepcopy(rb);bad['workshops']['screen-01']['rows'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):assert_readback(p,bad)

    def test_snapshot_extract_supports_native_and_wrapped_fields(self):
        p,rb=self.package();snapshot,mapping=self.snapshot(p,rb);original=copy.deepcopy(snapshot)
        extracted=extract_readback(p,snapshot,mapping)
        self.assertEqual(extracted,rb);self.assertEqual(snapshot,original)
        for i,node in enumerate(snapshot['canvas']['nodes']):
            snapshot['canvas']['nodes'][i]={'id':node['id'],'type':node['type'],'data':{k:v for k,v in node.items() if k not in ('id','type')}}
        self.assertEqual(extract_readback(p,snapshot,mapping),rb)

    def test_snapshot_export_preserves_evidence_and_refuses_overwrite(self):
        p,rb=self.package();snapshot,mapping=self.snapshot(p,rb)
        snap=self.root/'snapshot.json';snap.write_text(json.dumps(snapshot),encoding='utf-8')
        ids=self.root/'ids.json';ids.write_text(json.dumps(mapping),encoding='utf-8')
        out=self.root/'verified.json'
        result=readback_export(self.root/'package/package.json',snap,ids,out)
        self.assertEqual(result['readback'],'exact_match');self.assertFalse(result['paid_submission'])
        before=out.read_bytes()
        with self.assertRaises(ValueError):readback_export(self.root/'package/package.json',snap,ids,out)
        self.assertEqual(before,out.read_bytes())

    def test_wrong_mapping_and_duplicate_snapshot_ids_rejected(self):
        p,rb=self.package();snapshot,mapping=self.snapshot(p,rb)
        bad=copy.deepcopy(mapping);bad[p['tasks'][0]['gen_ref']]='workshop'
        with self.assertRaises(ValueError):extract_readback(p,snapshot,bad)
        snapshot['canvas']['nodes'].append(snapshot['canvas']['nodes'][0])
        with self.assertRaisesRegex(ValueError,'Duplicate snapshot'):extract_readback(p,snapshot,mapping)

    def test_reference_attachment_requires_replace_and_rejects_duplicate_bytes(self):
        p,_=self.package()
        self.assertIs(p['reference_attachments'][0]['arguments']['replace'],True)
        self.assertEqual(p['reference_attachments'][0]['arguments']['paths'],[str(self.root/'product.png')])
        self.m['tasks'][0]['references'].append(copy.deepcopy(self.m['tasks'][0]['references'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate input'):validate(self.m)
        other=self.root/'product-copy.png';shutil.copyfile(self.root/'product.png',other)
        self.m['tasks'][0]['references'][1]['path']=str(other)
        with self.assertRaisesRegex(ValueError,'Duplicate input'):validate(self.m)

    def test_loader_residue_and_workshop_residue_are_both_rejected(self):
        p,rb=self.package();snapshot,mapping=self.snapshot(p,rb)
        snapshot['canvas']['nodes'][0]['images'].append({'path':str(self.root/'master.png')})
        with self.assertRaisesRegex(ValueError,'reference order/content'):extract_readback(p,snapshot,mapping)
        snapshot,mapping=self.snapshot(p,rb)
        snapshot['canvas']['nodes'][2]['rows'][0]['images'].append(str(self.root/'master.png'))
        with self.assertRaisesRegex(ValueError,'input images/order'):extract_readback(p,snapshot,mapping)

    def test_one_snapshot_verifies_eight_production_tasks_and_names_outlier(self):
        from test_fixtures import workshop_fixture,bind_review_fixture
        self.m['ready_stage']='production'
        self.m['tasks']=[dict(copy.deepcopy(self.m['tasks'][0]),id=f'screen-{i:02d}') for i in range(1,9)]
        bind_review_fixture(self.m,self.root)
        result=compile_tasks(self.m,self.root/'batch')
        p=json.loads(Path(result['package']).read_text(encoding='utf-8'))
        operations={op.get('clientRef'):op for op in p['operations'] if op['op']=='createNode'}
        snapshot={'canvas':{'nodes':[]}};mapping={}
        for task in p['tasks']:
            sid=task['id'];ids=[sid+'-loader',sid+'-generator',sid+'-workshop']
            mapping.update(zip((task['load_ref'],task['gen_ref'],task['workshop_ref']),ids))
            snapshot['canvas']['nodes'].extend([
                {'id':ids[0],'type':'image/load-image-grid','images':[{'path':r['path']} for r in task['references']]},
                dict(operations[task['gen_ref']]['data'],id=ids[1],type='ai-image/gpt-image'),
                dict(workshop_fixture(task),id=ids[2],type='image/workshop')])
        self.assertEqual(len(extract_readback(p,snapshot,mapping)['workshops']),8)
        snapshot['canvas']['nodes'][-1]['rows'][0]['params']['model']='gpt-image-2-4k-qy'
        with self.assertRaisesRegex(ValueError,'screen-08: effective model'):
            extract_readback(p,snapshot,mapping)

    def test_master_uses_2k_enterprise_sunburst_and_fixed_ratio(self):
        self.m['ready_stage']='master'
        self.m['tasks'][0].update(kind='master',model_id='gpt-image-2.5-qy',resolution='2K',aspect_ratio='9:21')
        p,rb=self.package();task=p['tasks'][0]
        self.assertEqual(p['execution_profile'],'pt25-stage-sunburst-v3')
        self.assertEqual(p['operations'][1]['data']['modelType'],'gpt-image-2.5-qy')
        self.assertEqual(task['workshop_settings'],{'model':'gpt-image-2.5-qy','resolution':'2K','quality':'auto','gptStyle':'sunburst','transparent':False,'aspectRatio':'9:21'})
        self.assertEqual(assert_readback(p,rb)['readback'],'exact_match')
        for changes in ({'resolution':'1K'},{'resolution':'4K'},{'model_id':'gpt-image-2.5-1k-qy'},{'aspect_ratio':'9:16'},{'aspect_ratio':'1:3'}):
            m=copy.deepcopy(self.m);m['tasks'][0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate(m)

    def test_final_page_ratios_do_not_change_other_settings(self):
        for ratio in ('9:16',):
            m=copy.deepcopy(self.m);m['tasks'][0]['aspect_ratio']=ratio
            result=compile_tasks(m,self.root/('ratio-'+ratio.replace(':','-')))
            p=json.loads(Path(result['package']).read_text(encoding='utf-8'))
            settings=p['tasks'][0]['workshop_settings']
            self.assertEqual(settings,{'model':'gpt-image-2.5-1k-qy','resolution':'1K','quality':'auto','gptStyle':'sunburst','transparent':False,'aspectRatio':ratio})
        m=copy.deepcopy(self.m);m['tasks'][0]['resolution']='2K'
        with self.assertRaises(ValueError):validate(m)

    def test_none_style_or_transparency_override_rejected(self):
        for changes in ({'gpt_style':'none'},{'transparent':True},{'quality':'high'}):
            m=copy.deepcopy(self.m);m['tasks'][0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate(m)

    def test_sunburst_effective_alias_must_match_stage_family_and_resolution(self):
        p,rb=self.package()
        row=rb['workshops']['screen-01']['rows'][0]
        row['params']['model']='gpt-image-2.5-1k-sunburst-qy'
        self.assertEqual(assert_readback(p,rb)['readback'],'exact_match')
        for wrong in ('gpt-image-2.5-2k-sunburst-qy','gpt-image-2.5-1k-sunburst-wd','gpt-image-2-4k-qy'):
            row['params']['model']=wrong
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):assert_readback(p,rb)

    def test_old_profile_can_be_inspected_but_is_not_new_default(self):
        p,rb=self.package()
        self.assertNotEqual(p['execution_profile'],'pt25-1k-enterprise-v1')
        p['execution_profile']='pt25-1k-enterprise-v1'
        p['tasks'][0].pop('gpt_style');p['tasks'][0].pop('workshop_settings')
        rb['workshops']['screen-01']['rows'][0]['params']['gptStyle']='none'
        self.assertEqual(assert_readback(p,rb)['readback'],'exact_match')

    def test_ui_placeholder_ratio_is_not_a_final_page_ratio(self):
        for ratio in ('1:1','1:3','3:4','9:21'):
            m=copy.deepcopy(self.m);m['tasks'][0]['aspect_ratio']=ratio
            with self.subTest(ratio=ratio),self.assertRaisesRegex(ValueError,'Final page ratio'):validate(m)


if __name__=='__main__':unittest.main()
