import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import data, paths, render, verify

FAMILY = {
    "id": "ZV", "file": "ZV Test", "title": "ZV Test", "wiki_page": "ZV_Test",
    "readme_label": "ZV Test", "sections": ["S"],
    "rows": [
        {"sku": "ZVA", "section": "S", "released": "2020", "steel": "X", "handle": "Y",
         "type": "Regular production", "qty": "", "alt": "", "src": "manual|ZVA"},
        {"sku": "ZVB", "section": "S", "released": "2021", "steel": "X", "handle": "Y",
         "type": "Regular production", "qty": "", "alt": "", "src": "manual|ZVB"},
    ],
}


def _fam():
    return json.loads(json.dumps(FAMILY))


class TempRepo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.families_dir = root / "families"
        self.data_dir = root / "data"
        self.catalogs_dir = root / "Catalogs"
        self.images_dir = self.catalogs_dir / "images"
        for d in (self.families_dir, self.data_dir, self.catalogs_dir, self.images_dir):
            d.mkdir(parents=True)
        for target, value in (
            ("FAMILIES", self.families_dir), ("DATA", self.data_dir),
            ("CATALOGS", self.catalogs_dir), ("IMAGES", self.images_dir),
            ("README", root / "README.md"),
        ):
            patcher = patch.object(paths, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.root = root

    def write_family(self, fam):
        (self.families_dir / f"{fam['id']}.json").write_text(json.dumps(fam), encoding="utf-8")

    def render_to_catalog(self, fam, images=None):
        text = render.render_family(fam, images or {})
        (self.catalogs_dir / f"{fam['file']}.md").write_text(text, encoding="utf-8")
        return text


class TestVerifyClean(TempRepo):
    def test_no_problems_when_consistent(self):
        fam = _fam()
        self.write_family(fam)
        self.render_to_catalog(fam)
        self.assertEqual(verify.run(), [])


class TestVerifyRenderDiff(TempRepo):
    def test_missing_catalog_file_reported(self):
        self.write_family(_fam())
        problems = verify.run()
        self.assertTrue(any("ZV" in p and "not exist" in p for p in problems))

    def test_stale_catalog_file_reported(self):
        fam = _fam()
        self.write_family(fam)
        (self.catalogs_dir / f"{fam['file']}.md").write_text("stale content\n", encoding="utf-8")
        problems = verify.run()
        self.assertTrue(any("differs" in p for p in problems))


class TestVerifyReadme(TempRepo):
    def test_out_of_date_table_reported(self):
        fam = _fam()
        self.write_family(fam)
        self.render_to_catalog(fam)
        (self.root / "README.md").write_text(
            "# Repo\n\n<!-- families:start -->\nstale\n<!-- families:end -->\n", encoding="utf-8")
        problems = verify.run()
        self.assertTrue(any("README" in p for p in problems))

    def test_up_to_date_table_not_reported(self):
        fam = _fam()
        self.write_family(fam)
        self.render_to_catalog(fam)
        table = render.render_readme_table([fam])
        (self.root / "README.md").write_text(
            f"# Repo\n\n<!-- families:start -->\n{table}\n<!-- families:end -->\n", encoding="utf-8")
        self.assertEqual(verify.run(), [])

    def test_missing_markers_not_reported(self):
        fam = _fam()
        self.write_family(fam)
        self.render_to_catalog(fam)
        (self.root / "README.md").write_text("# Repo\nno markers here\n", encoding="utf-8")
        self.assertEqual(verify.run(), [])


class TestVerifyImages(TempRepo):
    def test_deleted_image_file_reports_broken_link_and_missing_record(self):
        fam = _fam()
        self.write_family(fam)
        img_path = self.images_dir / "ZV" / "ZVA.jpg"
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"fake")
        images = {"ZVA": {"file": "images/ZV/ZVA.jpg", "extra": []}}
        data.save_images(images)
        self.render_to_catalog(fam, images)

        img_path.unlink()
        problems = verify.run()
        self.assertTrue(any("broken image link" in p and "ZVA.jpg" in p for p in problems))
        self.assertTrue(any("missing file" in p and "ZVA.jpg" in p for p in problems))

    def test_image_record_for_unknown_sku_reported(self):
        fam = _fam()
        self.write_family(fam)
        self.render_to_catalog(fam)
        img_path = self.images_dir / "ZV" / "ZVZZZ.jpg"
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"fake")
        data.save_images({"ZVZZZ": {"file": "images/ZV/ZVZZZ.jpg", "extra": []}})
        problems = verify.run()
        self.assertTrue(any("ZVZZZ" in p and "not a SKU" in p for p in problems))


class TestVerifyRowIssues(TempRepo):
    def test_duplicate_src_reported(self):
        fam = _fam()
        fam["rows"][1]["src"] = fam["rows"][0]["src"]
        self.write_family(fam)
        self.render_to_catalog(fam)
        problems = verify.run()
        self.assertTrue(any("duplicate src" in p for p in problems))

    def test_duplicate_sku_same_released_reported(self):
        fam = _fam()
        fam["rows"][1].update(sku="ZVA", released="2020")
        self.write_family(fam)
        self.render_to_catalog(fam)
        self.assertTrue(any("duplicate sku 'ZVA'" in p for p in verify.run()))

    def test_duplicate_sku_different_released_ok(self):
        fam = _fam()
        fam["rows"][1]["sku"] = "ZVA"
        self.write_family(fam)
        self.render_to_catalog(fam)
        self.assertEqual(verify.run(), [])

    def test_row_without_src_reported(self):
        fam = _fam()
        del fam["rows"][0]["src"]
        self.write_family(fam)
        self.render_to_catalog(fam)
        problems = verify.run()
        self.assertTrue(any("no src" in p for p in problems))

    def test_unknown_section_reported(self):
        fam = _fam()
        fam["rows"][0]["section"] = "Nope"
        self.write_family(fam)
        problems = verify.run()
        self.assertTrue(any("unknown section" in p for p in problems))


def _real_family_ids():
    if not (paths.FAMILIES / "_order.json").exists():
        return []
    return data.all_family_ids()


@unittest.skipUnless(_real_family_ids(), "families/ is empty; run `spy.py seed-from-md` first")
class TestVerifySeededRepo(unittest.TestCase):
    def test_no_problems(self):
        self.assertEqual(verify.run(), [])


if __name__ == "__main__":
    unittest.main()
