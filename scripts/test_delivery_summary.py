"""Quantity reporting across final delivery and repairs; fake generation only."""
import copy
from pathlib import Path
import unittest
from delivery_summary import summarize,human_summary
from starcanvas_adapter import compile_tasks,read,sha
from starcanvas_executor import Executor,atomic_json
import test_executor as fixtures


class DeliverySummaryTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.ExecutorTests();f.setUp();f.prepare(2)
        f.worker.run(execute=True,max_wait=10,poll_interval=1)
        self.f=f;self.rows=[read(t['return_path'])['images'][0] for t in f.worker.state['tasks'].values()]
        self.delivery=f.root/'final.json';atomic_json(self.delivery,{'images':self.rows})
    def test_counts_have_no_currency_fields(self):
        r=summarize([self.f.folder],self.delivery)
        self.assertEqual((r['generated_image_count'],r['confirmed_generation_tasks'],r['final_delivered_image_count']),(2,2,2))
        self.assertFalse(any(word in k for k in r for word in ('coin','billing','charged','refund','unbilled')))
    def test_duplicate_run_and_output_records_do_not_double_count(self):
        r=summarize([self.f.folder,self.f.folder],self.delivery)
        self.assertEqual(r['confirmed_generation_tasks'],2);self.assertEqual(r['generated_image_count'],2)
        self.assertEqual(r['generation_attempts_recorded'],2)
    def test_repairs_count_toward_generation_but_only_selected_pages_delivered(self):
        f=self.f;m=copy.deepcopy(f.manifest);m['tasks']=m['tasks'][:1];m['ready_stage']='repair'
        m['repair_context']={'source_run':str(f.folder),'issues':{'screen-01':'Offline corrected copy'}}
        m['repair_authorization']={'mode':'explicit','evidence':'Offline one repair allowance','task_ids':['screen-01'],'max_generations':1}
        p=compile_tasks(m,f.root/'repair-package')['package'];folder=f.root/'repair-run';folder.mkdir()
        w=Executor(f.server,folder,clock=f.clock,sleep=f.clock.sleep);w.prepare(p);w.run(execute=True,max_wait=10,poll_interval=1)
        replacement=read(w.state['tasks']['screen-01']['return_path'])['images'][0]
        atomic_json(self.delivery,{'images':[replacement,self.rows[1]]})
        r=summarize([f.folder,folder],self.delivery)
        self.assertEqual(r['generated_image_count'],3);self.assertEqual(r['confirmed_generation_tasks'],3)
        self.assertEqual(r['final_delivered_image_count'],2);self.assertEqual(r['repair_generation_tasks'],1)
    def test_unknown_submission_stays_in_quantity_report(self):
        state=read(self.f.folder/'state.json')
        state['batches'].append({'id':'unknown-batch','local_ids':['unknown-page']})
        atomic_json(self.f.folder/'state.json',state)
        r=summarize([self.f.folder],self.delivery)
        self.assertEqual(r['unconfirmed_attempts'],1);self.assertFalse(r['image_count_complete'])

    def test_legacy_currency_fields_are_not_rendered(self):
        r=summarize([self.f.folder],self.delivery)
        r.update(star_coins_status='verified',actual_star_coins='123')
        text=human_summary(r)
        self.assertIn('最终交付：2 张',text)
        for word in ('星币','费用','待核对','消耗','账单'):self.assertNotIn(word,text)

    def test_cli_reports_counts_without_billing_option(self):
        import subprocess,sys
        script=Path(__file__).with_name('delivery_summary.py');out=self.f.root/'summary'
        proc=subprocess.run([sys.executable,'-X','utf8',str(script),'--runs',str(self.f.folder),
            '--delivery',str(self.delivery),'--output',str(out)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual({p.name for p in out.iterdir()},{'交付统计.txt','usage-summary.json'})
        self.assertNotIn('星币',proc.stdout)
        help_=subprocess.run([sys.executable,str(script),'--help'],capture_output=True,text=True)
        self.assertNotIn('--billing',help_.stdout)

if __name__=='__main__':unittest.main()
