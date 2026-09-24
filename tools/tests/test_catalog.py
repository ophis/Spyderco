import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import catalog, paths

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MIN = (FIXTURES / "family_min.md").read_text(encoding="utf-8")
ROW2 = "| 2 |  | ZTESTGP2 | Mar. 2022 | M390 | Red G-10 | 🟦 Blade HQ excl. |  |  |"
CONFIG = {"id": "ZTEST", "wiki_page": "ZTEST_Widget", "readme_label": "ZTEST Widget",
          "section_rules": [{"section": "Widget Lightweight", "field": "handle", "regex": "FRN"}],
          "aliases": {"ZTW": "ZTESTGP"}, "skip": [], "manual": [], "wiki_errors": {}}
X = Path("x.md")


def with_config(text, config=CONFIG):
    block = "<!-- spy\n" + json.dumps(config, ensure_ascii=False, indent=1) + "\n-->\n\n"
    title, rest = text.split("\n\n", 1)
    return f"{title}\n\n{block}{rest}"


class TestParseRender(unittest.TestCase):
    def test_real_catalogs_round_trip(self):
        files = sorted(paths.CATALOGS.glob("*.md"))
        self.assertEqual(len(files), 7)
        for path in files:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertEqual(catalog.render(catalog.parse(text, path)), text)

    def test_rows_images_and_types(self):
        cat = catalog.parse(MIN, X)
        self.assertIsNone(cat.config)
        self.assertEqual(cat.title, "ZTEST Widget — Widget & Widget Lightweight")
        self.assertEqual(cat.sections, ["Widget", "Widget Lightweight"])
        gp, gp2, lw = cat.rows
        self.assertEqual(gp.images, ["images/main.jpg", "images/extra.jpg"])
        self.assertEqual((gp2.images, gp2.type), ([], "Blade HQ excl."))
        self.assertEqual((lw.section, lw.type, lw.qty, lw.alt), ("Widget Lightweight", "Sprint Run", "500", "ZTLW (wiki)"))

    def test_config_comment_round_trip(self):
        text = with_config(MIN)
        cat = catalog.parse(text, X)
        self.assertEqual(cat.config, CONFIG)
        self.assertEqual(catalog.render(cat), text)
        cat.config = None
        self.assertEqual(catalog.render(cat), MIN)

    def test_render_renumbers_and_recounts(self):
        messy = MIN.replace("## Widget (2)", "## Widget (5)").replace("| 2 |  | ZTESTGP2", "| 9 |  | ZTESTGP2")
        self.assertEqual(catalog.render(catalog.parse(messy, X)), MIN)

    def test_no_trailing_newline_kept(self):
        text = MIN.rstrip("\n")
        self.assertEqual(catalog.render(catalog.parse(text, X)), text)

    def test_unknown_row_section_refused(self):
        cat = catalog.parse(MIN, X)
        cat.rows[0].section = "Nope"
        with self.assertRaises(catalog.CatalogError):
            catalog.render(cat)

    def test_malformed_input_names_file_and_line(self):
        cases = {
            "cells": MIN.replace(ROW2, ROW2.replace(" M390 |", "")),
            "tag": MIN.replace(ROW2, ROW2.replace("🟦 Blade HQ", "🟥 Blade HQ")),
            "image": MIN.replace(ROW2, ROW2.replace("|  | ZTESTGP2", '| <img src="a.jpg"> | ZTESTGP2')),
        }
        for name, text in cases.items():
            with self.subTest(case=name), self.assertRaisesRegex(catalog.CatalogError, r"x\.md:12:"):
                catalog.parse(text, X)
        with self.assertRaisesRegex(catalog.CatalogError, r"x\.md:7:"):
            catalog.parse(MIN.replace("## Widget (2)", "## Widget"), X)
        with self.assertRaisesRegex(catalog.CatalogError, r"x\.md:3:"):
            catalog.parse(with_config(MIN).replace("\n-->\n", "\n"), X)
        with self.assertRaisesRegex(catalog.CatalogError, r"x\.md:13:"):
            catalog.parse(MIN.replace(ROW2 + "\n", ROW2 + "\nstray note\n"), X)


class TestLoadSave(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "Catalogs").mkdir()
        for name, value in (("CATALOGS", root / "Catalogs"), ("README", root / "README.md")):
            p = patch.object(paths, name, value)
            p.start()
            self.addCleanup(p.stop)

    def write(self, file, id_):
        text = with_config(MIN, {**CONFIG, "id": id_, "readme_label": file}).replace("# ZTEST Widget", f"# {file}", 1)
        (paths.CATALOGS / f"{file}.md").write_text(text, encoding="utf-8")

    def test_all_ids_readme_order_then_file_name(self):
        for file, id_ in (("B two", "B2"), ("A one", "A1"), ("C three", "C3")):
            self.write(file, id_)
        (paths.CATALOGS / "notes.md").write_text("# Notes\n\nfree text\n", encoding="utf-8")
        paths.README.write_text("x\n<!-- families:start -->\n| Model | File | Variants |\n|---|---|---|\n"
                                "| C | [C three](Catalogs/C%20three.md) | 3 |\n<!-- families:end -->\n", encoding="utf-8")
        self.assertEqual(catalog.all_ids(), ["C3", "A1", "B2"])

    def test_save_unmodified_is_byte_identical_and_rebuilds_readme(self):
        self.write("A one", "A1")
        paths.README.write_text("x\n<!-- families:start -->\nold\n<!-- families:end -->\ny\n", encoding="utf-8")
        path = paths.CATALOGS / "A one.md"
        before = path.read_bytes()
        catalog.save(catalog.load("A1"))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(paths.README.read_text(encoding="utf-8"),
                         "x\n<!-- families:start -->\n| Model | File | Variants |\n|---|---|---|\n"
                         "| A one | [A one](Catalogs/A%20one.md) | 3 |\n<!-- families:end -->\ny\n")

    def test_unknown_and_duplicate_id(self):
        self.write("A one", "A1")
        with self.assertRaises(catalog.CatalogError):
            catalog.load("ZZ")
        self.write("A again", "A1")
        with self.assertRaisesRegex(catalog.CatalogError, "A1"):
            catalog.all_ids()


if __name__ == "__main__":
    unittest.main()
