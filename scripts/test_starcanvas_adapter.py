import copy,json,tempfile,unittest,time,os
from pathlib import Path
from starcanvas_adapter import compile_tasks,assert_readback,reconcile,validate,sha


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='detail-executor-'))
        self.prompt=self.root/'prompt.txt'
        self.prompt.write_bytes('原版规划\r\n标题：你好\n  精确空格\t主辅模块\\n字面转义'.encode('utf-8'))
        self.ref=self.root/'reference.bin';self.ref.write_bytes(b'fixture reference')
        self.item={'id':'slice01','kind':'slice','prompt_path':str(self.prompt),'model_id':'chosen','resolution':'1K','aspect_ratio':'9:21','references':[{'path':str(self.ref),'role':'product'}]}
        self.manifest={'version':1,'ready_stage':'sample','authority':'explicit test','legacy_experiment':{'evidence':'explicit offline legacy transport fixture'},'tasks':[self.item]}

    def package(self):
        result=compile_tasks(self.manifest,self.root/'package')
        return json.loads(Path(result['package']).read_text(encoding='utf-8'))

    def readbacks(self,p):
        return {'generators':{'slice01':p['operations'][1]['data']},'references':{'slice01':[r['path'] for r in p['tasks'][0]['references']]}}

    def test_preserve_prompt_bytes_and_order(self):
        self.item['references'].append({'path':str(self.ref),'role':'style'})
        p=self.package();node=p['operations'][1]['data']
        self.assertEqual(node['prompt'].encode('utf-8'),self.prompt.read_bytes())
        self.assertEqual([r['role'] for r in p['tasks'][0]['references']],['product','style'])
        self.assertFalse(p['paid_submission'])

    def test_no_planning_fields_required_or_rewritten(self):
        self.assertTrue(validate(self.manifest)['ready'])
        self.assertNotIn('primary_module',self.package())

    def test_main_image_mode_rejected(self):
        self.item['kind']='white'
        with self.assertRaises(ValueError):validate(self.manifest)

    def test_unready_dependency_not_parallelized(self):
        self.item['wait_for']=['slice02'];other=copy.deepcopy(self.item);other['id']='slice02'
        self.manifest['tasks'].append(other)
        with self.assertRaises(ValueError):validate(self.manifest)

    def test_completed_reference_dependency_allowed(self):
        self.item['wait_for']=['approved-master'];self.manifest['completed_dependencies']=['approved-master']
        self.assertTrue(validate(self.manifest)['ready'])

    def test_prompt_edit_after_package_is_rejected(self):
        p=self.package();n=p['operations'][1]['data'];self.prompt.write_bytes(b'changed')
        state=self.readbacks(p);state['generators']['slice01']=n
        with self.assertRaises(ValueError):assert_readback(p,state)

    def test_canvas_prompt_normalization_is_rejected(self):
        p=self.package();n=copy.deepcopy(p['operations'][1]['data']);n['prompt']=n['prompt'].replace('\r\n','\n')
        state=self.readbacks(p);state['generators']['slice01']=n
        with self.assertRaises(ValueError):assert_readback(p,state)

    def test_settings_change_rejected(self):
        p=self.package();n=copy.deepcopy(p['operations'][1]['data']);n['aspectRatio']='3:4'
        state=self.readbacks(p);state['generators']['slice01']=n
        with self.assertRaises(ValueError):assert_readback(p,state)

    def test_reference_content_change_rejected(self):
        p=self.package();state=self.readbacks(p);self.ref.write_bytes(b'changed')
        with self.assertRaises(ValueError):assert_readback(p,state)

    def test_reference_order_change_rejected(self):
        other=self.root/'other.bin';other.write_bytes(b'style');self.item['references'].append({'path':str(other),'role':'style'})
        p=self.package();state=self.readbacks(p);state['references']['slice01'].reverse()
        with self.assertRaises(ValueError):assert_readback(p,state)

    def test_original_package_preserved(self):
        self.package();before=sha(self.root/'package/package.json')
        with self.assertRaises(ValueError):compile_tasks(self.manifest,self.root/'package')
        self.assertEqual(before,sha(self.root/'package/package.json'))

    def test_duplicate_return_records_are_one_file_and_not_visual_approval(self):
        from PIL import Image
        p=self.package();folder=Path(p['tasks'][0]['output_dir']);folder.mkdir();image=folder/'result.png';Image.new('RGB',(90,210),'blue').save(image)
        state={'id_map':{'slice01-workshop':'workshop'},'runs':[{'nodeId':'workshop','taskId':'remote'}],'readbacks':self.readbacks(p)}
        record={'source':'generated','nodeId':'workshop','path':str(image)}
        snapshot={'remote':{'id':'remote','status':'done','startedAt':time.time()*1000,'endedAt':time.time()*1000,'outputs':{'generated':[record,record]}}}
        result=reconcile(p,state,snapshot,self.root/'return')
        self.assertEqual(len(result['images']),1);self.assertEqual(result['visual_status'],'needs_agent_review')

    def test_old_output_outside_attempt_is_rejected(self):
        from PIL import Image
        p=self.package();image=self.root/'old.png';Image.new('RGB',(90,210),'blue').save(image)
        state={'id_map':{'slice01-workshop':'workshop'},'runs':[{'nodeId':'workshop','taskId':'remote'}],'readbacks':self.readbacks(p)}
        snapshot={'remote':{'id':'remote','status':'done','startedAt':time.time()*1000,'endedAt':time.time()*1000,'outputs':{'generated':[{'source':'generated','nodeId':'workshop','path':str(image)}]}}}
        with self.assertRaises(ValueError):reconcile(p,state,snapshot,self.root/'return')

    def test_same_folder_stale_or_other_task_file_rejected(self):
        from PIL import Image
        p=self.package();folder=Path(p['tasks'][0]['output_dir']);folder.mkdir();image=folder/'old.png';Image.new('RGB',(90,210),'blue').save(image)
        state={'id_map':{'slice01-workshop':'workshop'},'runs':[{'nodeId':'workshop','taskId':'remote'}],'readbacks':self.readbacks(p)}
        row={'source':'generated','nodeId':'workshop','path':str(image),'taskId':'old-task'}
        snapshot={'remote':{'id':'remote','status':'done','startedAt':time.time()*1000,'endedAt':time.time()*1000,'outputs':{'generated':[row]}}}
        with self.assertRaises(ValueError):reconcile(p,state,snapshot,self.root/'return1')
        del row['taskId'];os.utime(image,(time.time()-60,time.time()-60))
        with self.assertRaises(ValueError):reconcile(p,state,snapshot,self.root/'return2')

    def test_return_without_readback_evidence_rejected(self):
        p=self.package()
        with self.assertRaises(KeyError):reconcile(p,{'id_map':{},'runs':[]},{},self.root/'return')


if __name__=='__main__':unittest.main(verbosity=2)
