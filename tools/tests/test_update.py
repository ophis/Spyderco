import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import data, paths, render, update, wiki

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REAL_FAMILIES = paths.FAMILIES
C99_WIKI = (FIXTURES / "update_wiki.txt").read_text(encoding="utf-8")


def _records(text):
    records = wiki.parse_tables(text)
    return records, wiki.source_keys(records)


class TempDirs(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.families = self.tmp / "families"
        self.families.mkdir()
        for name, value in (("FAMILIES", self.families), ("CACHE", self.tmp / "cache")):
            patcher = patch.object(paths, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_wiki(self, page, text):
        path = paths.CACHE / "wiki" / f"{page}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def quiet(self, fn, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = fn(*args, **kwargs)
        self.output = out.getvalue()
        return result

    def rows(self, id_):
        return data.load_family(id_)["rows"]

    def row(self, id_, src):
        return next(r for r in self.rows(id_) if r["src"] == src)


class TestSeededCompleteness(unittest.TestCase):
    def test_seeded_families_propose_nothing(self):
        for id_ in data.all_family_ids():
            fam = data.load_family(id_)
            with self.subTest(family=id_):
                d = update.diff(fam, *_records((FIXTURES / "wiki" / f"{fam['wiki_page']}.txt").read_text(encoding="utf-8")))
                self.assertEqual({k: d[k] for k in ("new", "changed", "gone", "relink")},
                                 {"new": [], "changed": [], "gone": [], "relink": []})


class TestC81Relink(TempDirs):
    def setUp(self):
        super().setUp()
        for p in REAL_FAMILIES.glob("*.json"):
            shutil.copy(p, self.families / p.name)
        text = (FIXTURES / "wiki" / "C81_Para-Military.txt").read_text(encoding="utf-8")
        self.write_wiki("C81_Para-Military", text.replace("C81FCGR2", "C81CFGR2"))

    def test_typo_fix_is_relink_not_new(self):
        self.quiet(update.run, "C81", offline=True)
        proposal = json.loads((paths.CACHE / "proposals" / "C81.json").read_text(encoding="utf-8"))
        self.assertEqual(proposal["relink"], [{"old": "wiki|C81FCGR2|2022", "new": ["wiki|C81CFGR2|2022"]}])
        self.assertEqual((proposal["new"], proposal["gone"], proposal["changed"]), ([], [], []))

        before = self.rows("C81")
        self.quiet(update.accept, "C81", [], all_new=True)
        self.assertEqual(self.rows("C81"), before)
        with self.assertRaises(ValueError):
            self.quiet(update.accept, "C81", ["wiki|C81CFGR2|2022"])

        self.quiet(update.accept, "C81", [], relink=("wiki|C81FCGR2|2022", "wiki|C81CFGR2|2022"))
        row = self.row("C81", "wiki|C81CFGR2|2022")
        self.assertEqual((row["sku"], row["alt"], row["type"]), ("C81CFGR2", "", "Smoky Mountain Knife Works excl."))
        self.assertEqual(row["src_raw"]["sku"], "C81CFGR2")
        self.assertEqual(len(self.rows("C81")), len(before))


class FixtureFamily(TempDirs):
    def setUp(self):
        super().setUp()
        shutil.copy(FIXTURES / "update_family.json", self.families / "C99.json")
        self.write_wiki("C99_Testmodel", C99_WIKI)
        self.fam = data.load_family("C99")


class TestDiff(FixtureFamily):
    def test_classification(self):
        d = update.diff(self.fam, *_records(C99_WIKI))
        self.assertEqual(d["new"], ["wiki|C99GPOR|2018", "wiki|C99GPSR|2020"])
        self.assertEqual(d["gone"], ["wiki|C99GPXX|2011"])
        self.assertEqual(d["relink"], [])
        self.assertEqual(d["changed"], [
            {"src": "wiki|C99GPBK|2014", "diff": {"from_to": ["2014-", "2014-2026"]}},
            {"src": "wiki|C99GPRD|2016", "diff": {"steel": ["CPM-S30V", "CPM-S45VN"]}},
        ])

    def test_occurrence_group_reorder_is_relink(self):
        records, _ = _records(C99_WIKI)
        i = next(n for n, r in enumerate(records) if r["sku"] == "C99GPCF")
        records[i], records[i + 1] = records[i + 1], records[i]
        d = update.diff(self.fam, records, wiki.source_keys(records))
        group = ["wiki|C99GPCF|2019", "wiki|C99GPCF|2019#2"]
        self.assertEqual(d["relink"], [{"old": s, "new": group} for s in group])
        self.assertFalse(set(group) & {c["src"] for c in d["changed"]})

    def test_occurrence_group_shrink_is_relink(self):
        records, _ = _records(C99_WIKI)
        records = [r for r in records if r["from_to"] != "2019-2021"]
        d = update.diff(self.fam, records, wiki.source_keys(records))
        self.assertEqual(d["relink"], [{"old": s, "new": ["wiki|C99GPCF|2019"]}
                                       for s in ("wiki|C99GPCF|2019", "wiki|C99GPCF|2019#2")])
        self.assertNotIn("wiki|C99GPCF|2019#2", d["gone"])

    def test_ignored_group_growth_is_new(self):
        records, _ = _records(C99_WIKI)
        dup = next(r for r in records if r["sku"] == "C99GPDUP")
        records.append({**dup, "from_to": "2021-2022"})
        d = update.diff(self.fam, records, wiki.source_keys(records))
        self.assertIn("wiki|C99GPDUP|2021#2", d["new"])
        self.assertNotIn("wiki|C99GPDUP|2021", d["new"])

    def test_non_wiki_rows_never_gone(self):
        d = update.diff(self.fam, *_records(C99_WIKI))
        self.assertNotIn("official|C99GPZZ", d["gone"])

    def test_classify_record_aliases_only_non_wiki(self):
        rec = {"sku": "C99GPORE", "handle": "Orange G-10", "table": "", "from_to": "2020", "steel": "", "note": "",
               "number_made": ""}
        self.assertEqual(update.classify_record(self.fam, rec, "wiki|C99GPORE|2020")["sku"], "C99GPORE")
        self.assertEqual(update.classify_record(self.fam, rec, "official|C99GPORE")["sku"], "C99GPOR")


class TestAccept(FixtureFamily):
    def run_update(self):
        self.quiet(update.run, "C99", offline=True)

    def test_new_inserted_by_date_with_alt(self):
        self.run_update()
        self.quiet(update.accept, "C99", [], all_new=True)
        skus = [r["sku"] for r in self.rows("C99") if r["section"] == "Testmodel"]
        self.assertEqual(skus, ["C99GP", "C99GPXX", "C99GPBK", "C99GPRD", "C99GPOR", "C99GPCF", "C99GPCF",
                                "C99GPSR", "C99GPZZ"])
        row = self.row("C99", "wiki|C99GPOR|2018")
        self.assertEqual(row["alt"], "C99GPOR (C99GOR) (wiki)")
        self.assertEqual(row["type"], "Blade HQ excl.")
        self.assertEqual(row["auto"]["sku"], "C99GPOR")

    def test_date_tie_inserts_after(self):
        self.quiet(update.add_row, "C99", {"sku": "C99GPTIE", "section": "Testmodel", "released": "2019"})
        skus = [r["sku"] for r in self.rows("C99") if r["section"] == "Testmodel"]
        self.assertEqual(skus[4:8], ["C99GPCF", "C99GPCF", "C99GPTIE", "C99GPZZ"])
        self.assertEqual(self.row("C99", "manual|C99GPTIE")["type"], "Regular production")

    def test_all_new_leaves_existing_rows_alone(self):
        self.run_update()
        before = {r["src"]: r for r in self.rows("C99")}
        self.quiet(update.accept, "C99", [], all_new=True)
        after = {r["src"]: r for r in self.rows("C99")}
        self.assertEqual({s: after[s] for s in before}, before)

    def test_changed_requires_flag(self):
        self.run_update()
        before = (paths.FAMILIES / "C99.json").read_bytes()
        with self.assertRaises(ValueError):
            self.quiet(update.accept, "C99", ["wiki|C99GPOR|2018", "wiki|C99GPBK|2014"])
        self.assertEqual((paths.FAMILIES / "C99.json").read_bytes(), before)

    def test_discontinuation_changed_same_src(self):
        self.run_update()
        self.quiet(update.accept, "C99", ["wiki|C99GPBK|2014"], changed=True)
        row = self.row("C99", "wiki|C99GPBK|2014")
        self.assertEqual((row["released"], row["src_raw"]["from_to"]), ("2014-2026", "2014-2026"))

    def test_corrected_field_kept(self):
        self.run_update()
        self.quiet(update.accept, "C99", [], changed=True)
        row = self.row("C99", "wiki|C99GPRD|2016")
        self.assertEqual(row["type"], "KnifeCenter excl.")
        self.assertEqual(row["steel"], "CPM-S45VN")
        self.assertEqual((row["auto"]["type"], row["auto"]["steel"]), ("Limited", "CPM-S45VN"))
        self.assertIn("kept: type", self.output)

    def test_stale_proposal(self):
        self.run_update()
        self.quiet(update.add_alias, "C99", "C99GPX", "C99GP")
        with self.assertRaises(update.StaleProposal):
            self.quiet(update.accept, "C99", [], all_new=True)

    def test_sequential_accepts_refresh_proposal(self):
        self.run_update()
        self.quiet(update.accept, "C99", ["wiki|C99GPOR|2018"])
        self.quiet(update.accept, "C99", ["wiki|C99GPSR|2020"])
        srcs = [r["src"] for r in self.rows("C99")]
        self.assertIn("wiki|C99GPOR|2018", srcs)
        self.assertIn("wiki|C99GPSR|2020", srcs)

    def test_group_relink_freed_key_becomes_new(self):
        rows = [r for r in self.fam["rows"] if r["src"] != "wiki|C99GPCF|2019#2"]
        self.fam["rows"] = rows
        data.save_family(self.fam)
        self.write_wiki("C99_Testmodel", C99_WIKI)
        self.run_update()
        self.quiet(update.accept, "C99", [], relink=("wiki|C99GPCF|2019", "wiki|C99GPCF|2019"))
        self.quiet(update.accept, "C99", ["wiki|C99GPCF|2019#2"])
        self.assertEqual(sum(r["sku"] == "C99GPCF" for r in self.rows("C99")), 2)


class TestNonWikiRelink(FixtureFamily):
    def setUp(self):
        super().setUp()
        self.quiet(update.add_row, "C99", {"sku": "C99GPSR", "section": "Testmodel", "released": "2020",
                                           "steel": "Hand steel", "qty": "500", "alt": "C99X"})
        self.quiet(update.run, "C99", offline=True)
        self.proposal = json.loads((paths.CACHE / "proposals" / "C99.json").read_text(encoding="utf-8"))

    def test_wiki_catch_up_is_relink_not_new(self):
        self.assertIn({"old": "manual|C99GPSR", "new": ["wiki|C99GPSR|2020"]}, self.proposal["relink"])
        self.assertEqual(self.proposal["new"], ["wiki|C99GPOR|2018"])

    def test_alias_match_is_relink(self):
        self.quiet(update.add_alias, "C99", "C99GPOX", "C99GPOR")
        self.quiet(update.add_row, "C99", {"sku": "C99GPOX", "section": "Testmodel", "released": "2018"})
        self.quiet(update.run, "C99", offline=True)
        proposal = json.loads((paths.CACHE / "proposals" / "C99.json").read_text(encoding="utf-8"))
        self.assertIn({"old": "manual|C99GPOX", "new": ["wiki|C99GPOR|2018"]}, proposal["relink"])
        self.assertEqual(proposal["new"], [])

    def test_all_new_leaves_one_row(self):
        self.quiet(update.accept, "C99", [], all_new=True)
        self.assertEqual(sum(r["sku"] == "C99GPSR" for r in self.rows("C99")), 1)
        self.assertIn("manual|C99GPSR", [r["src"] for r in self.rows("C99")])

    def test_relink_converts_and_preserves_fields(self):
        before = self.row("C99", "manual|C99GPSR")
        self.quiet(update.accept, "C99", [], relink=("manual|C99GPSR", "wiki|C99GPSR|2020"))
        self.assertNotIn("manual|C99GPSR", [r["src"] for r in self.rows("C99")])
        row = self.row("C99", "wiki|C99GPSR|2020")
        self.assertEqual({f: row[f] for f in (*update.ROW_FIELDS, "alt")},
                         {f: before[f] for f in (*update.ROW_FIELDS, "alt")})
        self.assertEqual(row["src_raw"], self.proposal["raw"]["wiki|C99GPSR|2020"])
        self.assertEqual(row["auto"]["sku"], "C99GPSR")


class TestCrossCheck(FixtureFamily):
    def test_unmatched(self):
        paths.CACHE.mkdir(exist_ok=True)
        (paths.CACHE / "official.json").write_text(json.dumps([
            {"title": "Testmodel", "handle": "t", "published": "", "skus": ["C99GP", "C99GPNEW", "C990X"], "images": []},
        ]), encoding="utf-8")
        (paths.CACHE / "forum.txt").write_text(
            "Testmodel CPM-M4 C99GPORE Blade HQ (USA) - JAN 2024\nTestmodel C99GPFRM Sprint Run (USA) - MAR 2025\n",
            encoding="utf-8")
        unmatched, notes = update.cross_check(self.fam)
        self.assertEqual([u["src"] for u in unmatched], ["official|C99GPNEW", "forum|C99GPFRM|MAR 2025"])
        self.assertEqual(notes, [])

    def test_absent_caches_noted(self):
        unmatched, notes = update.cross_check(self.fam)
        self.assertEqual(unmatched, [])
        self.assertEqual(len(notes), 2)


class TestEditCommands(FixtureFamily):
    def test_alias_ignore_add_row(self):
        update.add_alias("C99", "C99GPAAA", "C99GP")
        update.add_ignore("C99", "official|C99GPNEW")
        update.add_ignore("C99", "official|C99GPNEW")
        fam = data.load_family("C99")
        self.assertEqual(fam["aliases"]["C99GPAAA"], "C99GP")
        self.assertEqual(fam["ignore"].count("official|C99GPNEW"), 1)
        with self.assertRaises(ValueError):
            update.add_row("C99", {"sku": "C99GPM"})
        with self.assertRaises(ValueError):
            update.add_row("C99", {"sku": "C99GPM", "section": "Nope"})


class TestNewFamily(TempDirs):
    def test_init_update_accept_render(self):
        update.init_family("C99", "C99 Testmodel", "C99 Testmodel — Testmodel & Testmodel Lightweight",
                           "C99_Testmodel", ["Testmodel", "Testmodel Lightweight"],
                           ["Testmodel Lightweight:handle:FRN|FRCP"])
        with self.assertRaises(ValueError):
            update.init_family("C99", "x", "x", "x", ["S"], [])
        self.write_wiki("C99_Testmodel", C99_WIKI)
        self.quiet(update.run, "C99", offline=True)
        self.quiet(update.accept, "C99", [], all_new=True)
        fam = data.load_family("C99")
        expected = (FIXTURES / "c99_expected.md").read_text(encoding="utf-8")
        self.assertEqual(render.render_family(fam, {}), expected)
        self.quiet(update.run, "C99", offline=True)
        self.assertIn("nothing to propose", self.output)

    def test_offline_missing_cache_raises(self):
        update.init_family("C98", "C98 X", "C98 X", "C98_X", ["X"], [])
        with self.assertRaises(FileNotFoundError):
            self.quiet(update.run, "C98", offline=True)
        self.assertFalse((paths.CACHE / "proposals" / "C98.json").exists())

    def test_empty_wiki_refused(self):
        update.init_family("C98", "C98 X", "C98 X", "C98_X", ["X"], [])
        self.write_wiki("C98_X", "no tables here")
        with self.assertRaises(ValueError):
            self.quiet(update.run, "C98", offline=True)


if __name__ == "__main__":
    unittest.main()
