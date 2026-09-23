import unittest
from pathlib import Path

from lib import wiki

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "wiki_c101_excerpt.txt"


class TestClean(unittest.TestCase):
    def test_wikilink(self):
        self.assertEqual(wiki.clean("[[CPM-S30V]]"), "CPM-S30V")

    def test_external_link(self):
        self.assertEqual(wiki.clean("[https://x.com Foo]"), "Foo")

    def test_valign_and_bold(self):
        self.assertEqual(wiki.clean('valign="top" |\'\'\'C81GP2\'\'\''), "C81GP2")

    def test_leading_pipe(self):
        self.assertEqual(wiki.clean("|CPM 15V"), "CPM 15V")


class TestParseTables(unittest.TestCase):
    def setUp(self):
        self.wikitext = FIXTURE.read_text(encoding="utf-8")
        self.records = wiki.parse_tables(self.wikitext)

    def test_record_count(self):
        self.assertEqual(len(self.records), 9)

    def test_manix_table_heading(self):
        self.assertEqual(self.records[0]["table"], "Variations of the Manix 2")

    def test_military_table_heading(self):
        self.assertEqual(self.records[-1]["table"], "Variations")

    def test_standard_fields(self):
        first = self.records[0]
        self.assertEqual(first["sku"], "C101GP2")
        self.assertEqual(first["from_to"], "2009")
        self.assertEqual(first["number_made"], "50")

    def test_leading_pipe_steel_cell(self):
        record = next(r for r in self.records if r["sku"] == "C101GBN15V2")
        self.assertEqual(record["steel"], "CPM 15V")

    def test_fields_dict_has_cleaned_headers(self):
        self.assertIn("SKU", self.records[0]["fields"])
        self.assertEqual(self.records[0]["fields"]["SKU"], "C101GP2")

    def test_no_tables_raises(self):
        with self.assertRaises(ValueError):
            wiki.parse_tables("no tables here")


class TestSourceKeys(unittest.TestCase):
    def setUp(self):
        self.records = wiki.parse_tables(FIXTURE.read_text(encoding="utf-8"))
        self.keys = wiki.source_keys(self.records)

    def test_duplicate_c101gp2_2009(self):
        gp2_keys = [k for k, r in zip(self.keys, self.records) if r["sku"] == "C101GP2" and r["from_to"].startswith("2009")]
        self.assertEqual(gp2_keys, ["wiki|C101GP2|2009", "wiki|C101GP2|2009#2"])

    def test_forum_2000(self):
        idx = next(i for i, r in enumerate(self.records) if r["sku"] == "C36G (Forum 2000)")
        self.assertEqual(self.keys[idx], "wiki|C36G|2000")

    def test_unique_within_run(self):
        self.assertEqual(len(self.keys), len(set(self.keys)))


class TestRawOf(unittest.TestCase):
    def test_raw_of_keys(self):
        records = wiki.parse_tables(FIXTURE.read_text(encoding="utf-8"))
        raw = wiki.raw_of(records[0])
        self.assertEqual(
            set(raw.keys()),
            {"table", "sku", "handle", "edge", "steel", "from_to", "note", "number_made"},
        )
        self.assertEqual(raw["sku"], "C101GP2")


if __name__ == "__main__":
    unittest.main()
