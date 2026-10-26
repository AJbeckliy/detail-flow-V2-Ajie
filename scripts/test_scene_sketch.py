"""Relationship behavior checks, with no generation requests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from scene_sketch import prepare_scene
from render_layout_preview import render_plan


class SceneTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1]/'examples/scene-sketch.json'
        self.plan = json.loads(source.read_text(encoding='utf-8'))
        self.block = self.plan['pages'][2]['layout']['blocks'][0]

    def test_product_follows_neck_when_person_moves_and_mirrors(self):
        for facing in ['left', 'right']:
            b = copy.deepcopy(self.block)
            person = next(c for c in b['components'] if c['id']=='person')
            person.update(box=[.20,.25,.60,.60], facing=facing)
            items = {c['id']:c for c in prepare_scene(b)}
            x,y,w,h = items['product']['box']
            neck = items['person']['anchors']['neck']
            self.assertAlmostEqual(x+w/2, neck[0])
            self.assertAlmostEqual(y+h/2, neck[1])

    def test_invalid_relationships_and_geometry_rejected(self):
        cases = []
        for target in [{'component':'missing','anchor':'neck'},
                       {'component':'person','anchor':'invented'},
                       {'component':'product','anchor':'neck'}]:
            b=copy.deepcopy(self.block); b['components'][-1]['attach_to']=target; cases.append(b)
        b=copy.deepcopy(self.block); b['components'][0]['box']=[0,0,float('nan'),1]; cases.append(b)
        b=copy.deepcopy(self.block); b['components'][1]['points']=[[0,0],[2,0]]; cases.append(b)
        b=copy.deepcopy(self.block); b['components'][-1]['size']=[1,1]; cases.append(b)
        for b in cases:
            with self.subTest(block=b), self.assertRaises(ValueError): prepare_scene(b)

    def test_forward_attachment_retains_drawing_order_and_input(self):
        b=copy.deepcopy(self.block)
        b['components'].insert(0,b['components'].pop())
        before=copy.deepcopy(b)
        result=prepare_scene(b)
        self.assertEqual(result[0]['id'],'product')
        self.assertEqual(b,before)

    def test_full_sketch_render_and_invalid_sketch_blocks_output(self):
        root=Path(tempfile.mkdtemp(prefix='scene-sketch-test-'))
        source=root/'plan.json'
        source.write_text(json.dumps(self.plan),encoding='utf-8')
        result=render_plan(source,root/'valid')
        self.assertEqual(result['status'],'layout_ready_for_review')
        self.assertFalse(result['generation_authorized'])
        self.assertEqual(result['pages'][2]['text_exact'],self.plan['pages'][2]['text_exact'])
        self.block['components'][-1]['attach_to']['component']='missing'
        source.write_text(json.dumps(self.plan),encoding='utf-8')
        result=render_plan(source,root/'invalid')
        self.assertEqual(result['status'],'layout_needs_revision')
        self.assertIn('SKETCH_GEOMETRY',{i['code'] for i in result['issues']})
        self.assertFalse(list((root/'invalid').glob('*.png')))


if __name__=='__main__': unittest.main()
