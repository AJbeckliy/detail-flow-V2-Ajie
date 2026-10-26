"""Confirmed ratios remain on the stable MCP path, including same-canvas repairs."""
import copy
from pathlib import Path
import unittest
import test_stable_preview_fixes as fixtures
from starcanvas_adapter import compile_tasks,read,sha
from starcanvas_executor import Executor,atomic_json,verify_package


class ConfirmedRatioTests(unittest.TestCase):
    def fixture(self,ratio=None,master=False):
        f,m=fixtures.StableDefaultTests().make(master)
        if ratio:
            p=Path(m['approved_plan']['path']);plan=read(p);plan['aspect_ratio']=ratio;atomic_json(p,plan)
            m['approved_plan']['sha256']=sha(p);m['tasks'][0]['aspect_ratio']=ratio
        return f,m
    def test_every_cached_ratio_can_compile_prepare_and_collect(self):
        cache=read(Path(__file__).resolve().parents[1]/'references/model-settings.json')
        for ratio in cache['verified_ratios']:
            with self.subTest(ratio=ratio):
                f,m=self.fixture(ratio);path=compile_tasks(m,f.root/'package')['package']
                f.worker.prepare(path);result=f.worker.run(execute=True,max_wait=10,poll_interval=1)
                self.assertEqual(result['status'],'complete_needs_review')
                item=read(f.worker.state['tasks']['screen-01']['return_path'])['images'][0]
                a,b=map(int,ratio.split(':'));self.assertAlmostEqual(item['width']/item['height'],a/b)
                self.assertIn(ratio.replace(':','比'),f.worker.state['project_name'])
    def test_unspecified_defaults_and_explicit_plan_inheritance(self):
        for ratio in (None,'16:9'):
            f,m=self.fixture(ratio);m['tasks'][0].pop('aspect_ratio')
            p=read(compile_tasks(m,f.root/'package')['package'])
            self.assertEqual(p['tasks'][0]['aspect_ratio'],ratio or '9:16')
            self.assertNotIn('aspect_ratio',m['tasks'][0])
    def test_page_ratio_overrides_plan_default(self):
        f,m=self.fixture('16:9');path=Path(m['approved_plan']['path']);plan=read(path)
        plan['pages'][0]['aspect_ratio']='1:1';atomic_json(path,plan);m['approved_plan']['sha256']=sha(path)
        m['tasks'][0].pop('aspect_ratio')
        self.assertEqual(read(compile_tasks(m,f.root/'package')['package'])['tasks'][0]['aspect_ratio'],'1:1')
    def test_task_cannot_disagree_with_confirmed_plan(self):
        f,m=self.fixture('16:9');m['tasks'][0]['aspect_ratio']='9:16'
        with self.assertRaisesRegex(ValueError,'ratio differs'):compile_tasks(m,f.root/'package')
    def test_effective_ratio_drift_still_blocks_submission(self):
        f,m=self.fixture('16:9');f.worker.prepare(compile_tasks(m,f.root/'package')['package'])
        wid=f.worker.state['tasks']['screen-01']['node_id'];f.server.nodes[wid]['rows'][0]['params']['aspectRatio']='9:16'
        self.assertEqual(f.worker.run(execute=True,max_wait=10,poll_interval=1)['status'],'blocked')
        self.assertFalse(f.server.submissions)
    def test_horizontal_optional_preview(self):
        f,m=self.fixture('16:9',True);m['tasks'][0].pop('aspect_ratio')
        p=read(compile_tasks(m,f.root/'package')['package']);verify_package(p)
        self.assertEqual(p['tasks'][0]['aspect_ratio'],'16:9')
    def test_horizontal_repair_stays_on_same_canvas(self):
        f,m=self.fixture('16:9');f.worker.prepare(compile_tasks(m,f.root/'package')['package'])
        f.worker.run(execute=True,max_wait=10,poll_interval=1)
        repair=copy.deepcopy(m);repair.update(ready_stage='repair',repair_context={'source_run':str(f.folder),'issues':{'screen-01':'Offline typo repair'}},
            repair_authorization={'mode':'explicit','evidence':'Offline one repair','task_ids':['screen-01'],'max_generations':1})
        p=compile_tasks(repair,f.root/'repair-package')['package'];folder=f.root/'repair';folder.mkdir()
        w=Executor(f.server,folder,clock=f.clock,sleep=f.clock.sleep);w.prepare(p)
        self.assertEqual(w.state['project_id'],f.worker.state['project_id'])
        self.assertEqual(w.run(execute=True,max_wait=10,poll_interval=1)['status'],'complete_needs_review')
        self.assertEqual(w.package['tasks'][0]['aspect_ratio'],'16:9')
    def test_cache_is_not_a_second_hardcoded_ratio_gate(self):
        f,m=self.fixture('8:1');p=read(compile_tasks(m,f.root/'package')['package'])
        self.assertEqual(p['tasks'][0]['aspect_ratio'],'8:1')  # Actual platform preparation still decides support.
    def test_malformed_ratios_are_rejected(self):
        for ratio in ('auto','16/9','0:9','-1:2'):
            f,m=self.fixture();m['tasks'][0]['aspect_ratio']=ratio
            with self.subTest(ratio=ratio),self.assertRaises(ValueError):compile_tasks(m,f.root/'package')


if __name__=='__main__':unittest.main()
