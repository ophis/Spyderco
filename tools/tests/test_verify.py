import re
import unittest

from lib import catalog, paths, verify
from lib.catalog import Row
from tests.helpers import TempRepo, make_catalog


class TestVerify(TempRepo):
    def setUp(self):
        super().setUp()
        self.cat = make_catalog("ZV", "ZV Test", ["S"], [Row("ZVA", "S", "2020"), Row("ZVB", "S", "2021")])
        self.path = self.cat.path

    def edit(self, old, new):
        text = self.path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assertProblem(self, pattern):
        problems = verify.run()
        self.assertTrue(any(re.search(pattern, p) for p in problems), problems)

    def test_clean(self):
        self.assertEqual(verify.run(), [])

    def test_not_in_rendered_form(self):
        self.edit("## S (2)", "## S (3)")
        self.assertProblem("not in rendered form")

    def test_readme_out_of_date(self):
        paths.README.write_text("x\n<!-- families:start -->\nstale\n<!-- families:end -->\n", encoding="utf-8")
        self.assertProblem("README")

    def test_broken_image_link(self):
        self.cat.rows[0].images = ["images/ZV/ZVA.jpg"]
        catalog.save(self.cat)
        self.assertProblem("broken image link images/ZV/ZVA.jpg")
        (paths.IMAGES / "ZV").mkdir()
        (paths.IMAGES / "ZV" / "ZVA.jpg").write_bytes(b"x")
        self.assertEqual(verify.run(), [])

    def test_config_problems(self):
        original = self.path.read_text(encoding="utf-8")
        cases = {
            "unknown section 'Nope'": {"section_rules": [{"section": "Nope", "field": "sku", "regex": "x"}]},
            "bad section rule regex": {"section_rules": [{"section": "S", "field": "sku", "regex": "("}]},
            "field 'note'": {"section_rules": [{"section": "S", "field": "note", "regex": "x"}]},
            "missing config key 'wiki_page'": {"wiki_page": None},
            r"wiki_errors key 'ZVA\|1999' matches no row": {"wiki_errors": {"ZVA|1999": {"steel": "X"}}},
            "manual SKU 'ZVZ' matches no row": {"manual": ["ZVZ"]},
        }
        for pattern, change in cases.items():
            with self.subTest(pattern=pattern):
                cat = catalog.load("ZV")
                cat.config = {k: v for k, v in {**cat.config, **change}.items() if v is not None}
                self.path.write_text(catalog.render(cat), encoding="utf-8")
                self.assertProblem(pattern)
                self.path.write_text(original, encoding="utf-8")

    def test_duplicate_sku_same_released(self):
        self.cat.rows[1] = Row("ZVA", "S", "2020")
        catalog.save(self.cat)
        self.assertProblem("duplicate sku 'ZVA' with released '2020'")

    def test_duplicate_sku_different_released_ok(self):
        self.cat.rows[1] = Row("ZVA", "S", "2021")
        catalog.save(self.cat)
        self.assertEqual(verify.run(), [])

    def test_malformed_catalog_reported(self):
        self.edit("| 2 |", "| 2 | extra |")
        self.assertProblem(r"ZV Test\.md:\d+:")


if __name__ == "__main__":
    unittest.main()
