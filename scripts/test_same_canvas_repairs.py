"""Same-canvas repairs preserve original nodes and results; fake server only."""
import copy
from pathlib import Path
import unittest
import test_stable_preview_fixes as stable_fixtures
from starcanvas_adapter import compile_tasks,read,sha
from starcanvas_executor import Executor,atomic_json
from delivery_summary import summarize


class SameCanvasRepairTests(unittest.TestCase):
    def setUp(self):
        self.f,_=stable_fixtures.StableDefaultTests().make();self.f.prepare(2)
        self.f.worker.run(execute=True,max_wait=10,poll_interval=1)
    def manifest(self,source=None):
        f=self.f;m=copy.deepcopy(f.manifest);m['tasks']=m['tasks'][:1];m['ready_stage']='repair'
        m['repair_authorization']={'mode':'explicit','evidence':'Offline one repair approval','task_ids':['screen-01'],'max_generations':1}
        m['repair_context']={'source_run':str(source or f.folder),'issues':{'screen-01':'修正标题错字'}}
        return m
    def prepare(self,m,name='repair'):
        f=self.f;p=compile_tasks(m,f.root/(name+'-package'))['package'];folder=f.root/(name+'-run');folder.mkdir()
        w=Executor(f.server,folder,clock=f.clock,sleep=f.clock.sleep);w.prepare(p);return w
    def test_repair_reuses_project_and_keeps_old_nodes_images_prompts(self):
        f=self.f;before=copy.deepcopy(f.server.nodes)
        files={t['prompt_path']:sha(t['prompt_path']) for t in f.worker.package['tasks']}
        for local in f.worker.state['tasks'].values():
            row=read(local['return_path'])['images'][0];files[row['path']]=sha(row['path'])
        w=self.prepare(self.manifest())
        self.assertEqual(w.state['project_id'],f.worker.state['project_id'])
        self.assertEqual(sum(n=='project_create' for n,a in f.server.calls),1)
        self.assertEqual({k:f.server.nodes[k] for k in before},before)
        self.assertEqual(len(f.server.nodes),len(before)+4)
        new=[n for k,n in f.server.nodes.items() if k not in before]
        self.assertTrue(all(n['x']>max(n['x'] for n in before.values())+1000 for n in new if n['type']!='text/note'))
        note=next(n for n in new if n['type']=='text/note')
        self.assertIn('返修R1·第01屏\n问题：修正标题错字',note['content'])
        result=w.run(execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual(files,{p:sha(p) for p in files})
        trace=read(w.folder/'canvas-trace.json')
        self.assertEqual(trace['pages'][0]['source_nodes']['workshop'],f.worker.state['tasks']['screen-01']['node_id'])
        self.assertNotEqual(trace['pages'][0]['repair_nodes']['workshop'],trace['pages'][0]['source_nodes']['workshop'])
        calls=len(f.server.submissions);w.run(resume=True,max_wait=10,poll_interval=1)
        self.assertEqual(len(f.server.submissions),calls)
    def test_missing_original_node_blocks_without_new_project(self):
        f=self.f;f.server.nodes.pop(f.worker.state['id_map']['screen-01-gen'])
        creates=sum(n=='project_create' for n,a in f.server.calls)
        with self.assertRaisesRegex(ValueError,'Original source node missing'):self.prepare(self.manifest())
        self.assertEqual(sum(n=='project_create' for n,a in f.server.calls),creates)
    def test_repair_page_stays_aligned_with_its_source_row(self):
        m=self.manifest();m['tasks']=[copy.deepcopy(self.f.manifest['tasks'][1])]
        m['repair_context']['issues']={'screen-02':'修正第02屏配色'}
        m['repair_authorization']['task_ids']=['screen-02']
        w=self.prepare(m)
        old=self.f.server.nodes[self.f.worker.state['id_map']['screen-02-load']]
        new=self.f.server.nodes[w.state['id_map']['screen-02-load']]
        self.assertEqual(new['y'],old['y']);self.assertGreater(new['x'],old['x'])
    def test_missing_source_wrong_page_and_missing_reason_rejected(self):
        for mutate in ('missing_source','wrong_page','missing_reason'):
            m=self.manifest()
            if mutate=='missing_source':m['repair_context']['source_run']=str(self.f.root/'absent')
            if mutate=='wrong_page':m['tasks'][0]['page_id']='99'
            if mutate=='missing_reason':m['repair_context']['issues']={}
            with self.subTest(case=mutate),self.assertRaises(ValueError):compile_tasks(m,self.f.root/mutate)
    def test_source_identity_change_after_compile_blocks(self):
        p=compile_tasks(self.manifest(),self.f.root/'bound')['package']
        state=read(self.f.folder/'state.json');state['project_id']='different-project';atomic_json(self.f.folder/'state.json',state)
        folder=self.f.root/'changed-run';folder.mkdir()
        with self.assertRaisesRegex(ValueError,'binding changed'):Executor(self.f.server,folder).prepare(p)
    def test_second_repair_round_stays_on_same_canvas_and_counts_ancestors(self):
        first=self.prepare(self.manifest(),'repair-one');first.run(execute=True,max_wait=10,poll_interval=1)
        old=copy.deepcopy(self.f.server.nodes)
        second=self.prepare(self.manifest(first.folder),'repair-two')
        self.assertEqual(second.package['repair_context']['round'],2)
        self.assertEqual(second.state['project_id'],self.f.worker.state['project_id'])
        self.assertEqual({k:self.f.server.nodes[k] for k in old},old)
        second.run(execute=True,max_wait=10,poll_interval=1)
        usage=summarize([second.folder,first.folder,self.f.folder])
        self.assertEqual(usage['confirmed_generation_tasks'],4)
        self.assertEqual(usage['repair_generation_tasks'],2)
        self.assertEqual(sum(n=='project_create' for n,a in self.f.server.calls),1)
    def test_new_repair_without_binding_is_not_compiled(self):
        m=self.manifest();m.pop('repair_context')
        with self.assertRaisesRegex(ValueError,'original canvas'):compile_tasks(m,self.f.root/'unbound')


if __name__=='__main__':unittest.main()
