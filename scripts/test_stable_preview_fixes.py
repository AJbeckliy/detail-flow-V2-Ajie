"""Real image decoding, stable defaults and bounded legacy preview regression."""
import copy
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from starcanvas_adapter import compile_tasks,read,sha,LOCKED_PROFILE
from render_layout_preview import audit_plan,choose_font,draw_page
from master_fallback import run_chain,service_failure
from starcanvas_executor import Executor
import test_executor as execution
import test_master_fallback as legacy


class PreviewImageTests(unittest.TestCase):
    def setUp(self):self.root=Path(tempfile.mkdtemp(prefix='detail-preview-fix-'))
    def preview(self,p):
        plan={'aspect_ratio':'9:16','pages':[{'slice_id':'01','text_exact':{},'layout':{'blocks':[
            {'id':'image','type':'image','path':str(p),'box':[.1,.1,.8,.8]}]}}]}
        before=sha(p);pages,issues=audit_plan(plan,self.root,720,choose_font())
        self.assertFalse(issues);self.assertEqual(before,sha(p))
        return pages[0]['blocks'][0],draw_page(pages[0],choose_font())
    def test_phone_jpeg_orientation_is_used_for_geometry(self):
        p=self.root/'photo.jpg';exif=Image.Exif();exif[274]=6
        Image.new('RGB',(120,80),'red').save(p,exif=exif)
        block,_=self.preview(p);self.assertEqual(block['image'].size,(80,120))
        x,y,r,b=block['content_rect'];self.assertAlmostEqual((r-x)/(b-y),2/3,places=2)
    def test_rgba_and_palette_transparency_match_preview_background(self):
        for mode in ('RGBA','P'):
            with self.subTest(mode=mode):
                p=self.root/(mode+'.png')
                if mode=='RGBA':
                    im=Image.new('RGBA',(120,80),(0,0,0,0));im.putpixel((50,50),(255,0,0,255));im.save(p)
                else:
                    im=Image.new('P',(120,80),0);im.putpalette([0,0,0,255,0,0]+[0]*762);im.putpixel((50,50),1);im.save(p,transparency=0)
                block,_=self.preview(p)
                self.assertEqual(block['image'].getpixel((0,0)),(225,234,242))
                self.assertEqual(block['image'].getpixel((50,50)),(255,0,0))
    def test_ordinary_rgb_is_not_recolored(self):
        p=self.root/'rgb.png';Image.new('RGB',(120,80),'blue').save(p)
        self.assertEqual(self.preview(p)[0]['image'].getpixel((0,0)),(0,0,255))


class StableDefaultTests(unittest.TestCase):
    def make(self,master=False):
        f=execution.ExecutorTests();f.setUp();m=f.manifest
        m.update(workflow='detail-flow-direct-v3');m.pop('execution_profile');m.pop('visual_master')
        m['tasks'][0].update(model_id='gpt-image-2.5-wd')
        if master:
            m.update(ready_stage='master',master_request={'evidence':'Offline user-requested preview fixture'})
            m['tasks'][0]['kind']='master'
        return f,m
    def test_new_production_prepares_and_executes_stable_only(self):
        f,m=self.make();p=compile_tasks(m,f.root/'stable')['package'];package=read(p)
        self.assertEqual(package['execution_profile'],LOCKED_PROFILE)
        f.worker.prepare(p);result=run_chain(f.worker,execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual(package['tasks'][0]['workshop_settings']['model'],'gpt-image-2.5-wd')
    def test_requested_stable_preview_stops_after_one_503(self):
        f,m=self.make(True);p=compile_tasks(m,f.root/'preview')['package'];f.worker.prepare(p)
        f.server.fail_nodes.update(f.worker.state['id_map'].values())
        result=run_chain(f.worker,execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'partial_failure');self.assertEqual(len(f.server.submissions),1)
        self.assertEqual(read(p)['master_fallback'],{'enabled':False,'max_attempts':1,'trigger':'confirmed_terminal_service_failure'})
        self.assertFalse((f.folder/'fallback-chain.json').exists())
    def test_stable_preview_rejects_unsupported_retry_policy(self):
        for policy in ({'enabled':True},{'enabled':False,'max_attempts':2}):
            f,m=self.make(True);m['master_fallback']=policy
            with self.assertRaises(ValueError):compile_tasks(m,f.root/'invalid')


class PreviewLimitTests(unittest.TestCase):
    def test_two_attempt_limit_survives_compile_and_resume(self):
        f=legacy.MasterFallbackTests().setup_worker(3)
        m=copy.deepcopy(f.manifest);m['master_fallback']={'enabled':True,'max_attempts':2}
        p=compile_tasks(m,f.root/'bounded')['package'];folder=f.root/'bounded-run';folder.mkdir()
        worker=Executor(f.server,folder,clock=f.clock,sleep=f.clock.sleep);worker.prepare(p)
        run_chain(worker,execute=True,max_wait=10,poll_interval=1)
        run_chain(worker,resume=True,max_wait=10,poll_interval=1)
        self.assertEqual(len(f.server.submissions),2);self.assertEqual(read(p)['master_fallback']['max_attempts'],2)
    def test_invalid_limits_fail_before_preparation(self):
        for limit in (True,0,-1,4,1.5,'2'):
            f=legacy.MasterFallbackTests().setup_worker(0)
            m=copy.deepcopy(f.manifest);m['master_fallback']={'enabled':True,'max_attempts':limit}
            with self.subTest(limit=limit),self.assertRaises(ValueError):compile_tasks(m,f.root/'bad-limit')
            self.assertFalse(f.server.submissions)
    def test_cancel_payment_timeout_errors_never_fall_back(self):
        for error in ('HTTP 503 request cancelled by user','500 operation canceled','503 insufficient funds',
                      '503 payment declined','503 timeout waiting for response','503 请求超时'):
            with self.subTest(error=error):
                self.assertFalse(service_failure(error))
                f=legacy.MasterFallbackTests().setup_worker(3,error)
                run_chain(f.worker,execute=True,max_wait=10,poll_interval=1)
                self.assertEqual(len(f.server.submissions),1)
        self.assertTrue(service_failure('503 upstream model service error'))


if __name__=='__main__':unittest.main()
