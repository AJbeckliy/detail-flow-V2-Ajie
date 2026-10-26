import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from build_review_editor import build_editor


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='review-builder-'))
        self.plan=json.loads((Path(__file__).resolve().parents[1]/'examples/scene-sketch.json').read_text(encoding='utf-8'))
        self.source=self.root/'plan.json'; self.output=self.root/'review.html'

    def build(self):
        self.source.write_text(json.dumps(self.plan,ensure_ascii=False),encoding='utf-8')
        before=self.source.read_bytes()
        build_editor(self.source,self.output)
        self.assertEqual(before,self.source.read_bytes())
        return self.output.read_text(encoding='utf-8')

    def test_embedded_backgrounds_and_downloadable_asset_paths(self):
        Image.new('RGB',(20,20),'white').save(self.root/'asset.png')
        block=next(b for b in self.plan['pages'][0]['layout']['blocks'] if b['type']=='placeholder')
        block.update(type='image',path='asset.png')
        html=self.build()
        payload=json.loads(html.split('<script id="data" type="application/json">')[1].split('</script>')[0])
        self.assertEqual(len(payload['backgrounds']),3)
        self.assertTrue(all(x.startswith('data:image/png;base64,') for x in payload['backgrounds']))
        b=next(b for b in payload['plan']['pages'][0]['layout']['blocks'] if b['type']=='image')
        self.assertEqual(Path(b['path']),self.root/'asset.png')

    def test_script_like_copy_cannot_break_data_element(self):
        self.plan['title']='</script><script>alert(1)</script>'
        html=self.build()
        self.assertNotIn(self.plan['title'],html)
        payload=json.loads(html.split('<script id="data" type="application/json">')[1].split('</script>')[0])
        self.assertEqual(payload['plan']['title'],self.plan['title'])

    def test_visual_blocks_are_independent_deletable_layers(self):
        html=self.build()
        payload=json.loads(html.split('<script id="data" type="application/json">')[1].split('</script>')[0])
        for page,layers in zip(self.plan['pages'],payload['visual_layers']):
            expected={b['id'] for b in page['layout']['blocks'] if b['type'] not in {'text','annotation'}}
            self.assertEqual(set(layers),expected)
            self.assertTrue(all(v.startswith('data:image/png;base64,') for v in layers.values()))

    def test_preserve_existing_review(self):
        self.build(); before=self.output.read_bytes()
        with self.assertRaises(ValueError):build_editor(self.source,self.output)
        self.assertEqual(before,self.output.read_bytes())

    def test_annotation_targets_are_exported_for_live_leaders(self):
        html=self.build()
        payload=json.loads(html.split('<script id="data" type="application/json">')[1].split('</script>')[0])
        self.assertEqual(len(payload['annotation_targets']),len(self.plan['pages']))
        for page,targets in zip(self.plan['pages'],payload['annotation_targets']):
            expected={b['id'] for b in page['layout']['blocks'] if b['type']=='annotation'}
            self.assertEqual(set(targets),expected)
            for point in targets.values():
                self.assertTrue(all(0 <= value <= 1 for value in point))

    def test_invalid_layout_does_not_create_editor(self):
        self.plan['pages'][0]['layout']['blocks'][0]['box']=[1,1,1,1]
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
