import json
from pathlib import Path
import tempfile
import unittest
from prepare_review import prepare_review
from starcanvas_adapter import validate_review_delivery, sha


class ReviewLaunchTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='detail-review-entry-'))
        self.plan=Path(__file__).resolve().parents[1]/'examples/layout-preview.json'

    def test_default_builds_editable_artifact_and_requests_open(self):
        calls=[]
        r=prepare_review(self.plan,self.root/'review',opener=lambda url,new:calls.append((url,new)) or True)
        self.assertEqual(r['open_status'],'launch_requested');self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0],Path(r['html_path']).as_uri())
        html=Path(r['html_path']).read_text(encoding='utf-8')
        self.assertIn('textarea',html);self.assertIn('id="export"',html);self.assertNotIn('/*__PAYLOAD__*/',html)
        self.assertFalse(r['generation_authorized']);self.assertFalse(r['user_open_verified'])
        self.assertEqual(json.loads(Path(r['receipt_path']).read_text(encoding='utf-8'))['artifact_kind'],'editable_html_review')

    def test_failed_opener_retains_html_and_pending_confirmation(self):
        r=prepare_review(self.plan,self.root/'failed',opener=lambda *a,**k:False)
        self.assertEqual(r['open_status'],'launch_failed');self.assertTrue(Path(r['html_path']).is_file())
        self.assertEqual(r['status'],'awaiting_design_review')

    def test_headless_does_not_claim_open_and_existing_review_is_preserved(self):
        r=prepare_review(self.plan,self.root/'headless',no_open=True,opener=lambda *a,**k:self.fail('Should not launch'))
        self.assertEqual(r['open_status'],'not_requested')
        before=Path(r['html_path']).read_bytes()
        with self.assertRaises(ValueError):prepare_review(self.plan,self.root/'headless')
        self.assertEqual(before,Path(r['html_path']).read_bytes())

    def test_static_image_cannot_satisfy_transport_review_gate(self):
        for delivery in (None,{'kind':'png'},{'kind':'user_alternative','evidence':''}):
            with self.subTest(delivery=delivery),self.assertRaises(ValueError):validate_review_delivery({'review_delivery':delivery})

    def test_real_html_receipt_is_bound_and_tampering_rejected(self):
        r=prepare_review(self.plan,self.root/'bound',no_open=True)
        delivery={'kind':'editable_html','receipt_path':r['receipt_path'],'receipt_sha256':sha(r['receipt_path']),'presentation_evidence':'Synthetic visible link fixture'}
        validate_review_delivery({'review_delivery':delivery})
        Path(r['html_path']).write_text('static preview only',encoding='utf-8')
        with self.assertRaises(ValueError):validate_review_delivery({'review_delivery':delivery})


if __name__=='__main__':unittest.main()
