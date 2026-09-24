import unittest

from lib import catalog, paths, update, verify, wiki

WIKI = paths.TOOLS / "tests" / "fixtures" / "wiki"
IDS = ["C81", "C223", "C101", "C229", "C36", "C85", "C240"]


class TestRealCatalogs(unittest.TestCase):
    def test_every_catalog_has_config_in_readme_order(self):
        self.assertEqual(catalog.all_ids(), IDS)

    def test_quiet_against_wiki_fixtures(self):
        for id_ in IDS:
            cat = catalog.load(id_)
            records = wiki.parse_tables((WIKI / f"{cat.config['wiki_page']}.txt").read_text(encoding="utf-8"))
            with self.subTest(family=id_):
                self.assertEqual(update.diff(cat, records, update.record_keys(records)),
                                 {"new": [], "diff": [], "orphan": []})

    def test_verify_clean(self):
        self.assertEqual(verify.run(), [])


if __name__ == "__main__":
    unittest.main()
