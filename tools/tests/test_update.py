import json
import shutil
import unittest
from dataclasses import asdict
from unittest.mock import patch

import spy
from lib import catalog, paths, update, wiki
from lib.catalog import Row
from tests.helpers import FIXTURES, TempRepo, make_catalog

C99_WIKI = (FIXTURES / "update_wiki.txt").read_text(encoding="utf-8")


class C99(TempRepo):
    def setUp(self):
        super().setUp()
        shutil.copy(FIXTURES / "catalogs" / "C99 Testmodel.md", paths.CATALOGS / "C99 Testmodel.md")
        self.md = paths.CATALOGS / "C99 Testmodel.md"
        self.write_wiki("C99_Testmodel", C99_WIKI)

    def run_update(self):
        return self.quiet(update.run, "C99", offline=True)

    def proposal(self):
        return json.loads((paths.CACHE / "proposals" / "C99.json").read_text(encoding="utf-8"))

    def rows(self):
        return catalog.load("C99").rows


class TestDiff(C99):
    def test_new_diff_orphan(self):
        self.run_update()
        p = self.proposal()
        self.assertEqual([n["key"] for n in p["new"]], ["C99GPOR|2018", "C99GPSR|2020"])
        self.assertEqual(p["new"][0]["row"], {
            "sku": "C99GPOR", "section": "Testmodel", "released": "June 2018", "steel": "CPM-REX45",
            "handle": "Orange G-10", "type": "Blade HQ excl.", "qty": "", "alt": "C99GPOR (C99GOR) (wiki)"})
        self.assertEqual([(d["sku"], d["field"], d["md"], d["wiki"]) for d in p["diff"]], [
            ("C99GPBK", "released", "2014-", "2014-2026"),
            ("C99GPRD", "steel", "CPM-S30V", "CPM-S45VN"),
            ("C99GPRD", "type", "KnifeCenter excl.", "Limited")])
        self.assertEqual(p["orphan"], ["C99GPXX"])
        self.assertIn("NEW C99GPOR|2018", self.output)
        self.assertIn("DIFF C99GPBK released: md='2014-' wiki='2014-2026'", self.output)
        self.assertIn("ORPHAN C99GPXX", self.output)

    def test_update_never_writes_the_catalog(self):
        before = self.md.read_bytes()
        self.run_update()
        self.assertEqual(self.md.read_bytes(), before)

    def test_duplicate_sku_pairs_in_order(self):
        records = wiki.parse_tables(C99_WIKI)
        paired, _ = update.match(catalog.load("C99"), records, update.record_keys(records))
        self.assertEqual((paired["C99GPCF|2019"], paired["C99GPCF|2019#2"]), (4, 5))

    def test_start_year_preferred(self):
        cat = make_catalog("C97", "C97 Year", ["S"], [Row("C97A", "S", "2015"), Row("C97A", "S", "2020")])
        records = [{"sku": "C97A", "from_to": "2020-"}, {"sku": "C97A", "from_to": "2015-2019"}]
        self.assertEqual(update.match(cat, records, ["C97A|2020", "C97A|2015"]), ({"C97A|2020": 1, "C97A|2015": 0}, []))

    def test_exact_released_beats_table_order(self):
        cat = make_catalog("C96", "C96 Same", ["S"], [Row("C96A", "S", "2023-"), Row("C96A", "S", "Nov. 17, 2023")])
        records = [{"sku": "C96A", "from_to": "Nov. 17, 2023"}, {"sku": "C96A", "from_to": "2023-"}]
        self.assertEqual(update.match(cat, records, ["C96A|2023", "C96A|2023#2"])[0], {"C96A|2023": 1, "C96A|2023#2": 0})

    def test_record_key_alias_beats_shared_wiki_sku(self):
        cat = make_catalog("C95", "C95 Key", ["S"], [Row("C95BK", "S", "2024"), Row("C95SAT", "S", "2025")],
                           aliases={"C95BK|2025": "C95SAT"})
        records = [{"sku": "C95BK", "from_to": "2024"}, {"sku": "C95BK", "from_to": "2025"}]
        self.assertEqual(update.match(cat, records, ["C95BK|2024", "C95BK|2025"])[0], {"C95BK|2024": 0, "C95BK|2025": 1})

    def test_alias_and_alt_token_match(self):
        self.quiet(update.add_row, "C99", {"sku": "C99GPORX", "section": "Testmodel", "released": "June 2018"})
        self.quiet(update.add_alias, "C99", "C99GPOR", "C99GPORX")
        self.quiet(update.add_row, "C99", {"sku": "C99GPSRP", "section": "Testmodel", "released": "Nov. 2020",
                                           "alt": "C99GPSR (wiki)"})
        self.run_update()
        self.assertEqual(self.proposal()["new"], [])

    def test_skip_hides_record(self):
        self.quiet(update.add_skip, "C99", "C99GPOR|2018")
        self.quiet(update.add_skip, "C99", "C99GPOR|2018")
        self.assertEqual(catalog.load("C99").config["skip"], ["C99GPDUP|2021", "C99GPOR|2018"])
        self.run_update()
        self.assertEqual([n["key"] for n in self.proposal()["new"]], ["C99GPSR|2020"])

    def test_manual_hides_orphan(self):
        with self.assertRaises(ValueError):
            update.add_manual("C99", "C99NOPE")
        self.quiet(update.add_manual, "C99", "C99GPXX")
        self.run_update()
        self.assertEqual(self.proposal()["orphan"], [])


class TestWikiErrors(C99):
    def test_recorded_error_suppressed_until_wiki_changes(self):
        self.run_update()
        self.quiet(update.wiki_error, "C99", "C99GPRD", ["type"])
        self.assertEqual(catalog.load("C99").config["wiki_errors"], {"C99GPRD|March 2016": {"type": "Limited"}})
        self.run_update()
        self.assertEqual([(d["sku"], d["field"]) for d in self.proposal()["diff"]],
                         [("C99GPBK", "released"), ("C99GPRD", "steel")])
        self.write_wiki("C99_Testmodel", C99_WIKI.replace('|valign="top" |Limited run.', '|valign="top" |Sprint run'))
        self.run_update()
        self.assertIn(("C99GPRD", "type", "Sprint Run"),
                      [(d["sku"], d["field"], d["wiki"]) for d in self.proposal()["diff"]])

    def test_take_copies_wiki_value_and_renames_error_key(self):
        cat = catalog.load("C99")
        cat.config["wiki_errors"] = {"C99GPBK|2014-": {"steel": "Plain"}}
        catalog.save(cat)
        self.run_update()
        self.quiet(update.take, "C99", "C99GPBK", ["released"])
        cat = catalog.load("C99")
        self.assertEqual(next(r for r in cat.rows if r.sku == "C99GPBK").released, "2014-2026")
        self.assertEqual(cat.config["wiki_errors"], {"C99GPBK|2014-2026": {"steel": "Plain"}})
        self.assertNotIn("C99GPBK", [d["sku"] for d in self.proposal()["diff"]])

    def test_take_unproposed_field_refused(self):
        self.run_update()
        with self.assertRaises(ValueError):
            update.take("C99", "C99GPBK", ["steel"])

    def test_take_ambiguous_released_needs_flag(self):
        self.run_update()
        p = self.proposal()
        p["diff"].append({**p["diff"][0], "released": "2030"})
        (paths.CACHE / "proposals" / "C99.json").write_text(json.dumps(p), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "--released"):
            update.take("C99", "C99GPBK", ["released"])
        self.quiet(update.take, "C99", "C99GPBK", ["released"], released="2014-")


class TestAccept(C99):
    def test_all_new_inserted_by_date_existing_rows_untouched(self):
        self.run_update()
        before = [asdict(r) for r in self.rows()]
        self.quiet(update.accept, "C99", [], all_new=True)
        rows = self.rows()
        self.assertEqual([r.sku for r in rows if r.section == "Testmodel"],
                         ["C99GP", "C99GPXX", "C99GPBK", "C99GPRD", "C99GPOR", "C99GPCF", "C99GPCF", "C99GPSR", "C99GPZZ"])
        self.assertEqual([asdict(r) for r in rows if r.sku not in ("C99GPOR", "C99GPSR")], before)
        self.assertEqual(self.proposal()["new"], [])

    def test_unknown_key_refused_file_unchanged(self):
        self.run_update()
        before = self.md.read_bytes()
        with self.assertRaises(ValueError):
            update.accept("C99", ["C99GPOR|2018", "C99NOPE|2000"])
        self.assertEqual(self.md.read_bytes(), before)

    def test_stale_proposal(self):
        self.run_update()
        self.quiet(update.add_alias, "C99", "C99GPX", "C99GP")
        for fn, args in ((update.accept, (["C99GPOR|2018"],)), (update.take, ("C99GPBK", ["released"])),
                         (update.wiki_error, ("C99GPBK", ["released"]))):
            with self.subTest(fn=fn.__name__), self.assertRaises(update.StaleProposal):
                fn("C99", *args)

    def test_sequential_commands_refresh_proposal(self):
        self.run_update()
        self.quiet(update.accept, "C99", ["C99GPOR|2018"])
        self.quiet(update.wiki_error, "C99", "C99GPRD", ["steel", "type"])
        self.quiet(update.accept, "C99", ["C99GPSR|2020"])
        self.assertTrue({"C99GPOR", "C99GPSR"} <= {r.sku for r in self.rows()})

    def add_duplicate_new(self):
        p = self.proposal()
        p["new"].append({"key": "C99GPBK|2014#2", "row": {**p["new"][0]["row"], "sku": "C99GPBK", "released": "2014-"}})
        (paths.CACHE / "proposals" / "C99.json").write_text(json.dumps(p), encoding="utf-8")

    def test_duplicate_new_refused_by_key_file_unchanged(self):
        self.run_update()
        self.add_duplicate_new()
        before = self.md.read_bytes()
        with self.assertRaisesRegex(ValueError, "C99GPBK\\|2014#2"):
            update.accept("C99", ["C99GPOR|2018", "C99GPBK|2014#2"])
        self.assertEqual(self.md.read_bytes(), before)

    def test_all_new_skips_duplicate_and_keeps_it_proposed(self):
        self.run_update()
        self.add_duplicate_new()
        self.quiet(update.accept, "C99", [], all_new=True)
        self.assertEqual([r.sku for r in self.rows()].count("C99GPBK"), 1)
        self.assertEqual([n["key"] for n in self.proposal()["new"]], ["C99GPBK|2014#2"])
        self.assertIn("DUPLICATE C99GPBK|2014#2", self.output)

    def test_take_released_onto_existing_row_refused(self):
        self.quiet(update.add_row, "C99", {"sku": "C99GPBK", "section": "Testmodel", "released": "2014-2026"})
        self.run_update()
        p = self.proposal()
        p["diff"] = [{"sku": "C99GPBK", "released": "2014-", "field": "released", "md": "2014-", "wiki": "2014-2026"}]
        (paths.CACHE / "proposals" / "C99.json").write_text(json.dumps(p), encoding="utf-8")
        before = self.md.read_bytes()
        with self.assertRaisesRegex(ValueError, "already released"):
            update.take("C99", "C99GPBK", ["released"], released="2014-")
        self.assertEqual(self.md.read_bytes(), before)

    def test_new_row_inherits_same_sku_images(self):
        cat = catalog.load("C99")
        for r in cat.rows:
            if r.sku == "C99GPCF":
                r.images = ["images/C99/C99GPCF.jpg"]
        catalog.save(cat)
        self.quiet(update.add_row, "C99", {"sku": "C99GPCF", "section": "Testmodel", "released": "2024"})
        self.assertEqual([r.images for r in self.rows() if r.sku == "C99GPCF"], [["images/C99/C99GPCF.jpg"]] * 3)


class TestEditCommands(C99):
    def test_add_row(self):
        self.quiet(update.add_row, "C99", {"sku": "C99GPTIE", "section": "Testmodel", "released": "2019"})
        rows = self.rows()
        self.assertEqual([r.sku for r in rows][4:8], ["C99GPCF", "C99GPCF", "C99GPTIE", "C99GPZZ"])
        self.assertEqual(next(r for r in rows if r.sku == "C99GPTIE").type, "Regular production")
        self.assertIn("C99GPTIE", catalog.load("C99").config["manual"])
        for bad in ({"sku": "C99GPM"}, {"sku": "C99GPM", "section": "Nope"},
                    {"sku": "C99GPTIE", "section": "Testmodel", "released": "2019"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                update.add_row("C99", bad)

    def test_alias_sorted(self):
        update.add_alias("C99", "C99GPAAA", "C99GP")
        self.assertEqual(list(catalog.load("C99").config["aliases"]), ["C99GPAAA", "C99GPORE"])


class TestCrossCheck(C99):
    def test_unmatched_and_skip(self):
        (paths.CACHE / "official.json").write_text(json.dumps([
            {"title": "T", "handle": "t", "published": "", "skus": ["C99GP", "C99GPNEW", "C990X"], "images": []}]),
            encoding="utf-8")
        (paths.CACHE / "forum.txt").write_text(
            "Testmodel CPM-M4 C99GPORE Blade HQ (USA) - JAN 2024\nTestmodel C99GPFRM Sprint Run (USA) - MAR 2025\n",
            encoding="utf-8")
        self.assertEqual(update.cross_check(catalog.load("C99")),
                         ([{"source": "official", "sku": "C99GPNEW"}, {"source": "forum", "sku": "C99GPFRM"}], []))
        self.quiet(update.add_skip, "C99", "C99GPNEW")
        self.assertEqual(update.cross_check(catalog.load("C99"))[0], [{"source": "forum", "sku": "C99GPFRM"}])

    def test_absent_caches_noted(self):
        unmatched, notes = update.cross_check(catalog.load("C99"))
        self.assertEqual((unmatched, len(notes)), ([], 2))


class TestNewFamily(TempRepo):
    def test_init_update_accept(self):
        path = update.init_catalog("C99", "C99 Testmodel", "C99 Testmodel — T", "C99_Testmodel",
                                   ["Testmodel", "Testmodel Lightweight"], ["Testmodel Lightweight:handle:FRN|FRCP"])
        self.assertEqual(path, paths.CATALOGS / "C99 Testmodel.md")
        self.assertIn("| C99 Testmodel | [C99 Testmodel](Catalogs/C99%20Testmodel.md) | 0 |",
                      paths.README.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            update.init_catalog("C99", "C99 Testmodel", "x", "x", ["S"], [])
        with self.assertRaises(ValueError):
            update.init_catalog("C98", "C98 X", "x", "x", ["S"], ["Nope:handle:x"])
        self.assertFalse((paths.CATALOGS / "C98 X.md").exists())
        self.write_wiki("C99_Testmodel", C99_WIKI)
        self.quiet(update.run, "C99", offline=True)
        self.quiet(update.accept, "C99", [], all_new=True)
        self.assertEqual([(r.section, r.sku) for r in catalog.load("C99").rows],
                         [("Testmodel", s) for s in ("C99GP", "C99GPBK", "C99GPRD", "C99GPOR", "C99GPCF", "C99GPCF",
                                                     "C99GPSR", "C99GPDUP")] + [("Testmodel Lightweight", "C99PBK")])
        self.quiet(update.run, "C99", offline=True)
        self.assertIn("nothing to propose", self.output)

    def test_offline_missing_cache_and_empty_wiki(self):
        update.init_catalog("C98", "C98 X", "C98 X", "C98_X", ["X"], [])
        with self.assertRaises(FileNotFoundError):
            self.quiet(update.run, "C98", offline=True)
        self.write_wiki("C98_X", "no tables here")
        with self.assertRaises(ValueError):
            self.quiet(update.run, "C98", offline=True)
        self.assertFalse((paths.CACHE / "proposals" / "C98.json").exists())

    def test_fetch_failure_exits_nonzero_without_proposal(self):
        update.init_catalog("C98", "C98 X", "C98 X", "C98_X", ["X"], [])
        with patch.object(wiki, "fetch", side_effect=RuntimeError("fetch failed for 'C98_X': offline")):
            code = self.quiet(spy.main, ["update", "C98"])
        self.assertEqual(code, 1)
        self.assertIn("fetch failed", self.output)
        self.assertFalse((paths.CACHE / "proposals" / "C98.json").exists())


if __name__ == "__main__":
    unittest.main()
