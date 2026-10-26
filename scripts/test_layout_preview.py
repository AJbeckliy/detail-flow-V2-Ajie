"""Local layout behavior tests. No model or network requests; fixtures are synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from render_layout_preview import audit_plan, choose_font, leaves, render_plan


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="detail-layout-test-"))
        sample = Path(__file__).resolve().parents[1] / "examples/layout-preview.json"
        self.plan = json.loads(sample.read_text(encoding="utf-8"))
        self.font = choose_font()

    def audit(self, plan=None):
        return audit_plan(plan or self.plan, self.root, 720, self.font)

    def render(self, plan=None):
        source = self.root / "plan.json"
        source.write_text(json.dumps(plan or self.plan, ensure_ascii=False), encoding="utf-8")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        result = render_plan(source, self.root / "output", font_path=self.font)
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
        return result

    def codes(self, plan=None):
        return {x["code"] for x in self.audit(plan)[1]}

    def test_three_distinct_layouts_render_exact_copy_without_generation_authority(self):
        result = self.render()
        self.assertEqual(result["status"], "layout_ready_for_review")
        self.assertFalse(result["is_generated_image"])
        self.assertFalse(result["generation_authorized"])
        self.assertEqual(len(result["pages"]), 3)
        self.assertNotIn("REPEATED_GEOMETRY", self.codes())
        for original, rendered in zip(self.plan["pages"], result["pages"]):
            self.assertEqual(rendered["text_exact"], leaves(original["text_exact"]))
            with Image.open(rendered["path"]) as im:
                self.assertEqual(im.size, (720, 1280))

    def test_overflow_stops_images_instead_of_shortening_copy(self):
        page = self.plan["pages"][0]
        page["text_exact"]["headline"] = "必须原样保留的很长文案" * 40
        result = self.render()
        self.assertEqual(result["status"], "layout_needs_revision")
        self.assertIn("TEXT_OVERFLOW", {x["code"] for x in result["issues"]})
        self.assertFalse(list((self.root / "output").glob("*.png")))

    def test_out_of_bounds_and_nonfinite_geometry_rejected(self):
        for box in [[.9, .2, .3, .3], [0, 0, float("nan"), .3]]:
            with self.subTest(box=box):
                p = copy.deepcopy(self.plan)
                p["pages"][0]["layout"]["blocks"][0]["box"] = box
                self.assertIn("BLOCK_GEOMETRY", self.codes(p))

    def test_missing_and_unknown_copy_are_reported(self):
        self.plan["pages"][0]["text_exact"]["extra"] = "不可静默漏掉"
        self.plan["pages"][0]["layout"]["blocks"][0]["copy_key"] = "invented"
        self.assertTrue({"UNPLACED_COPY", "UNKNOWN_COPY"}.issubset(self.codes()))

    def test_duplicate_copy_is_reported(self):
        blocks = self.plan["pages"][0]["layout"]["blocks"]
        clone = dict(blocks[0], id="duplicate", box=[.05, .94, .9, .05])
        blocks.append(clone)
        self.assertIn("DUPLICATE_COPY", self.codes())

    def test_missing_layout_does_not_get_an_automatic_template(self):
        del self.plan["pages"][0]["layout"]
        self.assertIn("MISSING_LAYOUT", self.codes())

    def test_missing_image_is_not_replaced_with_a_fake_asset(self):
        block = self.plan["pages"][0]["layout"]["blocks"][-1]
        block.update(type="image", path="missing.png")
        self.assertIn("IMAGE_READ", self.codes())

    def test_annotation_maps_to_contained_image_not_entire_box(self):
        image = self.root / "wide.png"
        Image.new("RGB", (800, 400), "white").save(image)
        page = self.plan["pages"][1]
        page["layout"]["blocks"][0].update(type="image", path="wide.png")
        prepared, issues = self.audit()
        self.assertFalse([x for x in issues if x["severity"] == "error"])
        blocks = {b["id"]: b for b in prepared[1]["blocks"]}
        x0,y0,x1,y1 = blocks["product"]["content_rect"]
        self.assertLess(y1-y0, blocks["product"]["rect"][3]-blocks["product"]["rect"][1])
        self.assertEqual(blocks["label_a"]["target_point"],
                         (round(x0+.40*(x1-x0)), round(y0+.29*(y1-y0))))

    def test_annotation_unknown_visual_target_rejected(self):
        self.plan["pages"][1]["layout"]["blocks"][1]["target"]["block_id"] = "missing"
        self.assertIn("ANNOTATION_TARGET", self.codes())

    def test_intentional_overlap_requires_declaration(self):
        self.assertNotIn("UNDECLARED_OVERLAP", self.codes())
        self.plan["pages"][2]["layout"]["blocks"][1].pop("overlap_with")
        self.assertIn("UNDECLARED_OVERLAP", self.codes())

    def test_repeated_geometry_is_warning_not_silent_replanning(self):
        clone = copy.deepcopy(self.plan["pages"][0])
        clone["slice_id"] = "04"
        self.plan["pages"].append(clone)
        original = copy.deepcopy(self.plan)
        _, issues = self.audit()
        warning = next(x for x in issues if x["code"] == "REPEATED_GEOMETRY")
        self.assertEqual(warning["severity"], "warning")
        self.assertEqual(self.plan, original)

    def test_page_id_cannot_escape_output_directory(self):
        self.plan["pages"][0]["slice_id"] = "../escape"
        self.assertIn("PAGE_ID", self.codes())

    def test_existing_output_is_preserved(self):
        source = self.root / "plan.json"
        source.write_text(json.dumps(self.plan), encoding="utf-8")
        dest = self.root / "existing"
        dest.mkdir()
        marker = dest / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            render_plan(source, dest, font_path=self.font)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_confirmed_ratio_controls_page_dimensions(self):
        self.plan["pages"] = [self.plan["pages"][0]]
        self.plan["aspect_ratio"] = "9:21"
        result = self.render()
        self.assertEqual(result["pages"][0]["dimensions"], [720,1680])


if __name__ == "__main__":
    unittest.main(verbosity=2)
