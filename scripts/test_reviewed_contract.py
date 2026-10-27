import copy
from pathlib import Path
import unittest
from PIL import Image
import test_executor as execution
from starcanvas_adapter import compile_tasks,read,sha
from starcanvas_executor import atomic_json
from product_brief import create
from planning_checks import DISPLAY_TEXT,audit_plan,validate_visual_review


def fixture(count=1,mixed=False):
    f=execution.ExecutorTests();f.setUp();m=f.manifest;m.pop('visual_master');m.pop('execution_profile',None)
    m['workflow']='detail-flow-direct-v4';m['reference_policy']={'mode':'mixed' if mixed else 'text_only'}
    plan=create('Synthetic product',[f.root/'product.png'],pages=count)
    m['product_id']=plan['product_context']['product_id'];m['tasks']=[]
    Image.new('RGB',(90,160),'orange').save(f.root/'model.png')
    Image.new('RGB',(120,180),'purple').save(f.root/'reference.png')
    for i in range(1,count+1):
        pid=f'{i:02d}';refs=[{'role':'product','path':str(f.root/'product.png'),'sha256':sha(f.root/'product.png')}]
        if mixed:refs.append({'role':'composition','path':str(f.root/'reference.png'),'sha256':sha(f.root/'reference.png'),'purpose':'只借鉴俯拍食材排列','exclude':['不迁移品牌和功效']})
        page={'slice_id':pid,'module_type':'ingredient','visual_composition':('只展示食材特写，留出左侧说明区。' if i%2 else '食材分组置左，右侧为说明区。'),
              'product_display':'absent','text_exact':{'headline':'测试标题'+pid},'reference_images':copy.deepcopy(refs),
              'layout':{'blocks':[{'id':'headline','type':'text','copy_key':'headline','box':[.1,.05+i*.01,.8,.12],'font_size':24}]}}
        plan['pages'].append(page)
        prompt=f.root/('screen-'+pid+'.txt');prompt.write_text(page['text_exact']['headline']+'\n'+page['visual_composition']+'\n'+DISPLAY_TEXT['absent']+
            ('\n只借鉴俯拍食材排列；不迁移品牌和功效' if mixed else ''),encoding='utf-8')
        m['tasks'].append({'id':'screen-'+pid,'page_id':pid,'kind':'slice','model_id':'gpt-image-2.5-wd','resolution':'1K','aspect_ratio':'9:16',
                           'quality':'auto','prompt_path':str(prompt),'references':refs})
    plan_path=f.root/'current-plan.json';atomic_json(plan_path,plan)
    m['approved_plan']={'path':str(plan_path),'sha256':sha(plan_path),'approval_evidence':'Offline fixture approval; not real spending authority'}
    return f,m,plan,plan_path


class ReviewedContractTests(unittest.TestCase):
    def save(self,m,plan,path):atomic_json(path,plan);m['approved_plan']['sha256']=sha(path)
    def test_new_product_does_not_inherit_previous_horizontal_ratio(self):
        f,m,plan,path=fixture()
        first=create('Charger',[f.root/'product.png'],ratio='16:9',ratio_evidence='Current charger request')
        second=create('Jewelry',[f.root/'product.png'])
        self.assertEqual(first['aspect_ratio'],'16:9');self.assertEqual(second['aspect_ratio'],'9:16')
        self.assertNotEqual(first['product_context']['product_id'],second['product_context']['product_id'])
    def test_wrong_product_id_and_product_asset_are_rejected(self):
        f,m,plan,path=fixture();m['product_id']='previous-product'
        with self.assertRaisesRegex(ValueError,'Product ID'):compile_tasks(m,f.root/'bad-id')
        m['product_id']=plan['product_context']['product_id'];m['tasks'][0]['references'][0].update(path=str(f.root/'model.png'),sha256=sha(f.root/'model.png'))
        with self.assertRaisesRegex(ValueError,'inventory'):compile_tasks(m,f.root/'bad-product')
    def test_visual_intent_and_packaging_role_must_reach_prompt(self):
        for missing in ('visual','display'):
            f,m,plan,path=fixture();prompt=Path(m['tasks'][0]['prompt_path']);text=prompt.read_text(encoding='utf-8')
            prompt.write_text(text.replace(plan['pages'][0]['visual_composition'] if missing=='visual' else DISPLAY_TEXT['absent'],''),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'missing from prompt'):compile_tasks(m,f.root/'missing')
    def test_repeated_geometry_requires_reason_and_revised_flag_does_not_hide_it(self):
        f,m,plan,path=fixture(2);plan['pages'][1]['layout']=copy.deepcopy(plan['pages'][0]['layout']);self.save(m,plan,path)
        with self.assertRaisesRegex(ValueError,'Unresolved planning warning'):compile_tasks(m,f.root/'unresolved')
        plan['planning_review']={'decisions':{'repeated_geometry:02':{'action':'revised','reason':'Pretend fixed'}}};self.save(m,plan,path)
        with self.assertRaises(ValueError):compile_tasks(m,f.root/'pretend')
        plan['planning_review']['decisions']['repeated_geometry:02']={'action':'keep','reason':'Deliberate matched comparison geometry'};self.save(m,plan,path)
        self.assertEqual(read(compile_tasks(m,f.root/'allowed')['package'])['workflow'],'detail-flow-direct-v4')
    def test_model_role_and_mixed_reference_are_bound_and_transported(self):
        for mixed in (False,True):
            f,m,plan,path=fixture(mixed=mixed)
            model={'role':'model','path':str(f.root/'model.png'),'sha256':sha(f.root/'model.png'),'purpose':'只用于指定动物身份'}
            m['tasks'][0]['references'].append(model);plan['pages'][0]['reference_images'].append(copy.deepcopy(model));self.save(m,plan,path)
            prompt=Path(m['tasks'][0]['prompt_path']);prompt.write_text(prompt.read_text(encoding='utf-8')+'\n'+model['purpose'],encoding='utf-8')
            p=compile_tasks(m,f.root/'package')['package'];f.worker.prepare(p)
            self.assertEqual(f.worker.run(execute=True,max_wait=10,poll_interval=1)['status'],'complete_needs_review')
            self.assertEqual(f.worker.state['readbacks']['references']['screen-01'],[r['path'] for r in m['tasks'][0]['references']])
    def test_text_only_cannot_silently_attach_visual_reference(self):
        f,m,plan,path=fixture(mixed=True);m['reference_policy']['mode']='text_only'
        with self.assertRaisesRegex(ValueError,'mixed mode'):compile_tasks(m,f.root/'bad')
    def test_reference_order_or_role_changes_are_rejected(self):
        f,m,plan,path=fixture(mixed=True);m['tasks'][0]['references'][1]['role']='style'
        with self.assertRaisesRegex(ValueError,'references/order/roles'):compile_tasks(m,f.root/'role')
    def test_cropped_reference_original_is_frozen(self):
        from starcanvas_executor import verify_package
        f,m,plan,path=fixture(mixed=True)
        source=f.root/'reference-original.png';Image.new('RGB',(240,360),'purple').save(source)
        for ref in (m['tasks'][0]['references'][1],plan['pages'][0]['reference_images'][1]):
            ref.update(source_path=str(source),source_sha256=sha(source),crop_box=[0,0,.5,.5])
        self.save(m,plan,path)
        p=read(compile_tasks(m,f.root/'package')['package']);verify_package(p)
        Image.new('RGB',(240,360),'green').save(source)
        with self.assertRaisesRegex(ValueError,'original source changed'):verify_package(p)
    def test_invented_reference_weights_are_not_provider_controls(self):
        f,m,plan,path=fixture(mixed=True);m['tasks'][0]['references'][1]['weight']=.8
        with self.assertRaisesRegex(ValueError,'weight controls'):compile_tasks(m,f.root/'weight')
    def test_product_count_and_language_do_not_drift(self):
        f,m,plan,path=fixture();plan['product_context']['page_count']=2;self.save(m,plan,path)
        with self.assertRaisesRegex(ValueError,'page count'):compile_tasks(m,f.root/'count')
        plan['product_context']['page_count']=1;self.save(m,plan,path);m['tasks'][0]['language']='en-US'
        with self.assertRaisesRegex(ValueError,'language'):compile_tasks(m,f.root/'language')
    def test_repeat_typo_review_needs_changed_strategy_and_known_image(self):
        f,m,plan,path=fixture();image=f.root/'product.png'
        review={'set_coherence':'pass','pages':[{'id':'01','image_path':str(image),'sha256':sha(image),'technical':'pass',
          'copy':'needs_revision','product_identity':'pass','composition':'pass',
          'issues':[{'code':'headline:睛->晴','description':'点睛重复生成成点晴','repeated':True,'next_strategy':'same_prompt_again'}]}]}
        with self.assertRaisesRegex(ValueError,'changed repair strategy'):validate_visual_review(review)
        review['pages'][0]['issues'][0].update(next_strategy='targeted_text_edit',strategy_reason='评估仅修标题并复查整页，保留批准文案')
        self.assertEqual(validate_visual_review(review)['status'],'needs_revision')
        review['pages'][0]['copy']='pass'
        with self.assertRaisesRegex(ValueError,'Known issues'):validate_visual_review(review)

if __name__=='__main__':unittest.main()
