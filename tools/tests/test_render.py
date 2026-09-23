import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import data, paths, render

FIXTURES = Path(__file__).resolve().parent / "fixtures"

FIXTURE_IMAGES = {
    "ZTESTGP": {"file": "images/main.jpg", "extra": ["images/extra.jpg", "images/missing_extra.jpg"]},
    "ZTESTGP2": {"file": "images/missing_main.jpg", "extra": []},
}


def _load_fixture_family():
    return json.loads((FIXTURES / "family_min.json").read_text(encoding="utf-8"))


class TestRenderFamily(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(paths, "CATALOGS", FIXTURES)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_matches_golden_file(self):
        fam = _load_fixture_family()
        expected = (FIXTURES / "family_min.md").read_text(encoding="utf-8")
        self.assertEqual(render.render_family(fam, FIXTURE_IMAGES), expected)

    def test_missing_image_file_renders_empty_cell(self):
        fam = {
            "id": "ZMISS", "file": "ZMISS", "title": "ZMISS", "wiki_page": "ZMISS",
            "sections": ["S"],
            "rows": [{"sku": "ZMISSA", "section": "S", "released": "2020", "steel": "X",
                      "handle": "Y", "type": "Regular production", "qty": "", "alt": "", "src": "manual|ZMISSA"}],
        }
        images = {"ZMISSA": {"file": "images/does-not-exist.jpg", "extra": []}}
        out = render.render_family(fam, images)
        self.assertIn("| 1 |  | ZMISSA |", out)

    def test_no_image_record_renders_empty_cell(self):
        fam = _load_fixture_family()
        out = render.render_family(fam, {})
        self.assertIn("| 1 |  | ZTESTGP |", out)

    def test_trailing_newline_false_strips_final_newline(self):
        fam = _load_fixture_family()
        fam["trailing_newline"] = False
        out = render.render_family(fam, {})
        self.assertFalse(out.endswith("\n"))


class TestValidateFamily(unittest.TestCase):
    def test_valid_family_has_no_errors(self):
        self.assertEqual(data.validate_family(_load_fixture_family()), [])

    def test_missing_keys_reported(self):
        errors = data.validate_family({"id": "X"})
        self.assertTrue(any("file" in e for e in errors))
        self.assertTrue(any("rows" in e for e in errors))

    def test_unknown_section_reported(self):
        fam = _load_fixture_family()
        fam["rows"][0]["section"] = "Nonexistent"
        errors = data.validate_family(fam)
        self.assertTrue(any("unknown section" in e for e in errors))

    def test_duplicate_src_reported(self):
        fam = _load_fixture_family()
        fam["rows"][1]["src"] = fam["rows"][0]["src"]
        errors = data.validate_family(fam)
        self.assertTrue(any("duplicate src" in e for e in errors))


class TestLoadSaveFamily(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.families_dir = Path(tmp.name)
        patcher = patch.object(paths, "FAMILIES", self.families_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_then_load_roundtrip(self):
        fam = _load_fixture_family()
        data.save_family(fam)
        self.assertEqual(data.load_family("ZTEST"), fam)

    def test_save_writes_trailing_newline_and_indent(self):
        fam = _load_fixture_family()
        data.save_family(fam)
        text = (self.families_dir / "ZTEST.json").read_text(encoding="utf-8")
        self.assertEqual(json.dumps(fam, ensure_ascii=False, indent=1) + "\n", text)

    def test_load_invalid_json_raises_with_filename(self):
        (self.families_dir / "BAD.json").write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(data.FamilyError) as cm:
            data.load_family("BAD")
        self.assertIn("BAD.json", str(cm.exception))

    def test_load_validation_error_raises(self):
        (self.families_dir / "BAD2.json").write_text(json.dumps({"id": "BAD2"}), encoding="utf-8")
        with self.assertRaises(data.FamilyError) as cm:
            data.load_family("BAD2")
        self.assertIn("BAD2.json", str(cm.exception))


class TestAllFamilyIds(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.families_dir = Path(tmp.name)
        patcher = patch.object(paths, "FAMILIES", self.families_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_order_file_sorts_alphabetically_and_skips_underscore_files(self):
        for id_ in ("C240", "C81", "C101"):
            (self.families_dir / f"{id_}.json").write_text("{}", encoding="utf-8")
        (self.families_dir / "_scratch.json").write_text("{}", encoding="utf-8")
        self.assertEqual(data.all_family_ids(), ["C101", "C240", "C81"])

    def test_order_file_used_verbatim(self):
        order = ["C81", "C223", "C101", "C229", "C36", "C85", "C240"]
        (self.families_dir / "_order.json").write_text(json.dumps(order), encoding="utf-8")
        self.assertEqual(data.all_family_ids(), order)


class TestImagesStore(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name)
        patcher = patch.object(paths, "DATA", self.data_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_load_images_empty_when_missing(self):
        self.assertEqual(data.load_images(), {})

    def test_save_then_load_roundtrip(self):
        images = {"C81GP2": {"file": "images/C81/C81GP2.jpg", "extra": [], "url": "u", "src": "manual", "page": "p"}}
        data.save_images(images)
        self.assertEqual(data.load_images(), images)


class TestRenderReadmeTable(unittest.TestCase):
    def test_format(self):
        families = [
            {"readme_label": "C81 Para-Military / ParaMilitary 2", "file": "C81 Para-Military", "rows": [{}] * 3},
            {"readme_label": "C240 Smock", "file": "C240 Smock", "rows": [{}] * 11},
        ]
        lines = render.render_readme_table(families).split("\n")
        self.assertEqual(lines[0], "| Model | File | Variants |")
        self.assertEqual(lines[1], "|---|---|---|")
        self.assertEqual(
            lines[2],
            "| C81 Para-Military / ParaMilitary 2 | [C81 Para-Military](Catalogs/C81%20Para-Military.md) | 3 |",
        )
        self.assertEqual(lines[3], "| C240 Smock | [C240 Smock](Catalogs/C240%20Smock.md) | 11 |")


class TestWriteAll(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.families_dir = root / "families"
        self.data_dir = root / "data"
        self.catalogs_dir = root / "Catalogs"
        self.families_dir.mkdir()
        self.data_dir.mkdir()
        self.catalogs_dir.mkdir()
        for target, value in (
            ("FAMILIES", self.families_dir),
            ("DATA", self.data_dir),
            ("CATALOGS", self.catalogs_dir),
        ):
            patcher = patch.object(paths, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        fam = _load_fixture_family()
        (self.families_dir / "ZTEST.json").write_text(json.dumps(fam), encoding="utf-8")
        self._root = root

    def _patch_readme(self, text):
        readme_path = self._root / "README.md"
        readme_path.write_text(text, encoding="utf-8")
        patcher = patch.object(paths, "README", readme_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        return readme_path

    def test_writes_catalog_file(self):
        self._patch_readme("# Repo\n")
        written = render.write_all(["ZTEST"])
        catalog_path = self.catalogs_dir / "ZTEST Widget.md"
        self.assertIn(catalog_path, written)
        self.assertTrue(catalog_path.exists())

    def test_readme_updated_when_markers_present(self):
        readme_path = self._patch_readme(
            "# Repo\n\n<!-- families:start -->\nold\n<!-- families:end -->\n\nmore\n"
        )
        written = render.write_all(["ZTEST"])
        self.assertIn(readme_path, written)
        text = readme_path.read_text(encoding="utf-8")
        self.assertIn("ZTEST Widget", text)
        self.assertIn("more", text)
        self.assertNotIn("old", text)

    def test_readme_untouched_when_markers_absent(self):
        readme_path = self._patch_readme("# Repo\nno markers here\n")
        original = readme_path.read_text(encoding="utf-8")
        written = render.write_all(["ZTEST"])
        self.assertNotIn(readme_path, written)
        self.assertEqual(readme_path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
