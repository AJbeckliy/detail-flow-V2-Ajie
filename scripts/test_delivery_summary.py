"""Counts and bill attribution across final delivery and repairs; fake generation only."""
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
    def ledger(self,records):
        original=self.f.root/'platform-export.txt';original.write_text('Synthetic actual bill evidence for offline tests only',encoding='utf-8')
        p=self.f.root/'ledger.json';atomic_json(p,{'kind':'actual_platform_bill','currency':'star_coin',
            'evidence':{'path':str(original),'sha256':sha(original)},'records':records})
        return p
    def test_absent_bill_is_pending_not_zero(self):
        r=summarize([self.f.folder],self.delivery)
        self.assertEqual((r['generated_image_count'],r['confirmed_generation_tasks'],r['final_delivered_image_count']),(2,2,2))
        self.assertIsNone(r['actual_star_coins']);self.assertEqual(r['star_coins_status'],'pending_verification')
    def test_duplicate_run_and_output_records_do_not_double_count(self):
        r=summarize([self.f.folder,self.f.folder],self.delivery)
        self.assertEqual(r['confirmed_generation_tasks'],2);self.assertEqual(r['generated_image_count'],2)
        self.assertEqual(r['generation_attempts_recorded'],2)
    def test_actual_decimal_charges_and_refunds(self):
        bill=self.ledger([{'task_id':self.rows[0]['task_id'],'charged_star_coins':'12.5','refunded_star_coins':'2.5'},
                          {'task_id':self.rows[1]['task_id'],'charged_star_coins':'0'}])
        r=summarize([self.f.folder],self.delivery,bill)
        self.assertEqual(r['actual_star_coins'],'10.0');self.assertEqual(r['star_coins_status'],'verified')
    def test_partial_bill_is_not_presented_as_total(self):
        bill=self.ledger([{'task_id':self.rows[0]['task_id'],'charged_star_coins':12}])
        r=summarize([self.f.folder],self.delivery,bill)
        self.assertIsNone(r['actual_star_coins']);self.assertEqual(r['verified_partial_star_coins'],'12')
    def test_unknown_duplicate_and_invalid_amounts_are_rejected(self):
        row={'task_id':self.rows[0]['task_id'],'charged_star_coins':1}
        cases=[[dict(row,task_id='foreign')],[row,row],[dict(row,charged_star_coins=True)],
               [dict(row,charged_star_coins='NaN')],[dict(row,charged_star_coins=-1)],
               [dict(row,refunded_star_coins=2)]]
        for records in cases:
            bill=self.ledger(records)
            with self.subTest(records=records),self.assertRaises(ValueError):summarize([self.f.folder],self.delivery,bill)
    def test_billing_source_drift_and_estimates_are_rejected(self):
        bill=self.ledger([]);original=self.f.root/'platform-export.txt';original.write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError):summarize([self.f.folder],self.delivery,bill)
        bill=self.ledger([]);v=read(bill);v['kind']='estimate';atomic_json(bill,v)
        with self.assertRaises(ValueError):summarize([self.f.folder],self.delivery,bill)
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
    def test_unknown_submission_cannot_be_claimed_fully_billed(self):
        state=read(self.f.folder/'state.json')
        state['batches'].append({'id':'unknown-batch','local_ids':['unknown-page']})
        atomic_json(self.f.folder/'state.json',state)
        bill=self.ledger([{'task_id':r['task_id'],'charged_star_coins':0} for r in self.rows])
        r=summarize([self.f.folder],self.delivery,bill)
        self.assertEqual(r['unconfirmed_attempts'],1);self.assertIsNone(r['actual_star_coins'])


class HumanSummaryTests(unittest.TestCase):
    def result(self):
        return {'final_delivered_image_count':16,'generated_image_count':22,'confirmed_generation_tasks':20,
            'repair_generation_tasks':4,'preview_generation_tasks':0,'unconfirmed_attempts':0,'image_count_complete':True,
            'star_coins_status':'pending_verification','actual_star_coins':None,'verified_partial_star_coins':None}
    def test_unknown_or_partial_cost_is_omitted(self):
        for partial in (None,'12.5'):
            result=self.result();result['verified_partial_star_coins']=partial
            text=human_summary(result)
            self.assertIn('最终交付：16 张',text)
            for word in ('星币','待核对','费用','实际净消耗','已核实部分'):self.assertNotIn(word,text)
    def test_verified_total_including_zero_is_shown(self):
        for amount in ('0','12.5'):
            result=self.result();result.update(star_coins_status='verified',actual_star_coins=amount)
            self.assertIn('实际净消耗：'+amount+' 星币',human_summary(result))


if __name__=='__main__':unittest.main()
