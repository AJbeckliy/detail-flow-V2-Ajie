import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from compose_ordered_preview import compose


class OrderedPreviewTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='detail-vertical-test-'))
        Image.new('RGB',(120,240),'red').save(self.root/'red.png')
        Image.new('RGB',(240,240),'blue').save(self.root/'blue.png')
        self.items=[{'id':'02','path':'blue.png'},{'id':'01','path':'red.png'}]
        self.manifest=self.root/'order.json';self.output=self.root/'result'

    def run_compose(self):
        self.manifest.write_text(json.dumps({'images':self.items}),encoding='utf-8')
        return compose(self.manifest,self.output,width=120)

    def test_explicit_order_geometry_and_originals_preserved(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.glob('*.png')}
        r=self.run_compose()
        self.assertEqual([x['id'] for x in r['images']],['02','01'])
        self.assertEqual([x['y'] for x in r['images']],[0,120])
        with Image.open(r['preview_path']) as im:
            self.assertEqual(im.size,(120,360));self.assertEqual(im.getpixel((60,60)),(0,0,255));self.assertEqual(im.getpixel((60,240)),(255,0,0))
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.glob('*.png')})
        self.assertEqual(r['status'],'needs_agent_visual_review');self.assertFalse(r['generation_authorized'])

    def test_duplicate_ids_and_paths_rejected(self):
        self.items[1]['id']='02'
        with self.assertRaises(ValueError):self.run_compose()
        self.items[1]['id']='01';self.items[1]['path']='blue.png'
        with self.assertRaises(ValueError):self.run_compose()
        self.assertFalse(self.output.exists())

    def test_missing_file_or_empty_list_has_no_output(self):
        self.items[1]['path']='missing.png'
        with self.assertRaises(OSError):self.run_compose()
        self.items=[]
        with self.assertRaises(ValueError):self.run_compose()
        self.assertFalse(self.output.exists())

    def test_existing_preview_is_never_overwritten(self):
        r=self.run_compose();p=Path(r['preview_path']);before=p.read_bytes()
        with self.assertRaises(ValueError):self.run_compose()
        self.assertEqual(before,p.read_bytes())


if __name__=='__main__':unittest.main()
