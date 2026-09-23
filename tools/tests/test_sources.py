import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import paths, sources

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAKE_HELPER = FIXTURES / "fake_helper.py"


class TestParseProducts(unittest.TestCase):
    def setUp(self):
        self.pages = json.loads((FIXTURES / "products_page.json").read_text(encoding="utf-8"))

    def test_returns_trimmed_records_with_skus(self):
        products = sources.parse_products(self.pages)
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0]["skus"], ["C101GPFGBK2"])
        self.assertEqual(products[1]["skus"], ["C123TIPM390"])
        self.assertTrue(all({"title", "handle", "published", "skus", "images"} <= p.keys() for p in products))
        self.assertEqual(len(products[1]["images"]), 3)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            sources.parse_products([])


class TestParseForum(unittest.TestCase):
    def setUp(self):
        self.text = (FIXTURES / "forum_post.txt").read_text(encoding="utf-8")

    def test_finds_c85gptn2_mar_2021(self):
        records = sources.parse_forum(self.text)
        match = next(r for r in records if "C85GPTN2" in r["skus"])
        self.assertEqual(match["month_year"], "MAR 2021")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            sources.parse_forum("no release lines here\njust text\n")


class TempCache(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        patcher = patch.object(paths, "CACHE", self.tmp / "cache")
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_cmd(self):
        return [sys.executable, str(FAKE_HELPER)]

    def failing_cmd(self, code=4):
        return [sys.executable, "-c", f"import sys; sys.exit({code})"]


class TestRunHelper(TempCache):
    def test_success_returns_parsed_result(self):
        result = sources.run_helper("fake", {"exit": 0, "response": {"ok": True}}, cmd=self.fake_cmd())
        self.assertEqual(result, {"ok": True})

    def test_exit_2_raises_verification_error(self):
        with self.assertRaises(sources.FetchError) as cm:
            sources.run_helper("fake", {"exit": 2}, cmd=self.fake_cmd())
        self.assertIn("verification", str(cm.exception))

    def test_exit_3_raises_blocked_error(self):
        with self.assertRaises(sources.FetchError) as cm:
            sources.run_helper("fake", {"exit": 3}, cmd=self.fake_cmd())
        self.assertIn("403", str(cm.exception))

    def test_exit_4_raises_timeout_error(self):
        with self.assertRaises(sources.FetchError) as cm:
            sources.run_helper("fake", {"exit": 4}, cmd=self.fake_cmd())
        self.assertIn("timeout", str(cm.exception))

    def test_exit_1_raises_other_error(self):
        with self.assertRaises(sources.FetchError):
            sources.run_helper("fake", {"exit": 1}, cmd=self.fake_cmd())

    def test_job_written_with_result_path(self):
        sources.run_helper("fake", {"exit": 0, "response": []}, cmd=self.fake_cmd())
        jobs_dir = paths.CACHE / "jobs"
        job_files = list(jobs_dir.glob("*.json"))
        # one job file and one result file per call
        self.assertEqual(len(job_files), 2)


class TestFetchOfficialFailureLeavesCacheUntouched(TempCache):
    def test_pre_existing_cache_unchanged_on_failure(self):
        official_path = paths.CACHE / "official.json"
        official_path.parent.mkdir(parents=True, exist_ok=True)
        original = b'[{"title": "old", "handle": "old", "published": "2020", "skus": ["C1OLD"], "images": []}]\n'
        official_path.write_bytes(original)

        with self.assertRaises(sources.FetchError):
            sources.fetch_official(cmd=self.failing_cmd())

        self.assertEqual(official_path.read_bytes(), original)

    def test_fetch_official_writes_parsed_products_on_success(self):
        pages = json.loads((FIXTURES / "products_page.json").read_text(encoding="utf-8"))
        path = sources.fetch_official(cmd=[sys.executable, "-c", (
            "import json,sys; job=json.load(open(sys.argv[1])); "
            f"json.dump({json.dumps(pages)}, open(job['result'], 'w'))"
        )])
        self.assertEqual(path, paths.CACHE / "official.json")
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved[0]["skus"], ["C101GPFGBK2"])


class TestFetchForum(TempCache):
    def test_pre_existing_cache_unchanged_on_failure(self):
        forum_path = paths.CACHE / "forum.txt"
        forum_path.parent.mkdir(parents=True, exist_ok=True)
        original = b"old cached forum text\n"
        forum_path.write_bytes(original)

        with self.assertRaises(sources.FetchError):
            sources.fetch_forum(cmd=self.failing_cmd())

        self.assertEqual(forum_path.read_bytes(), original)

    def test_fetch_forum_writes_raw_text_on_success(self):
        text = (FIXTURES / "forum_post.txt").read_text(encoding="utf-8")
        path = sources.fetch_forum(cmd=[sys.executable, "-c", (
            "import json,sys; job=json.load(open(sys.argv[1])); "
            f"json.dump({{'text': {json.dumps(text)}}}, open(job['result'], 'w'))"
        )])
        self.assertEqual(path.read_text(encoding="utf-8"), text)


class TestSitemapLocs(unittest.TestCase):
    def test_extracts_and_unescapes_locs(self):
        xml = "<urlset><url><loc>https://x.com/a?x=1&amp;y=2</loc></url></urlset>"
        self.assertEqual(sources._sitemap_locs(xml), ["https://x.com/a?x=1&y=2"])

    def test_no_locs(self):
        self.assertEqual(sources._sitemap_locs("<urlset></urlset>"), [])


class TestNeedsBrowser(unittest.TestCase):
    def test_bladehq_needs_browser(self):
        self.assertTrue(sources._needs_browser("bladehq.com"))
        self.assertTrue(sources._needs_browser("www.bladehq.com"))

    def test_other_domain_does_not(self):
        self.assertFalse(sources._needs_browser("dltrading.com"))


if __name__ == "__main__":
    unittest.main()
