import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from lib import data, images, paths

FAMILY = {
    "id": "C81",
    "file": "C81 Para-Military",
    "title": "C81",
    "wiki_page": "C81_Para-Military",
    "sections": ["Para-Military"],
    "aliases": {"C81GPX": "C81GP"},
    "rows": [
        {"sku": "C81GP", "section": "Para-Military", "type": "Regular production", "src": "a"},
        {"sku": "C81GPBK2", "section": "Para-Military", "type": "Blade HQ excl.", "src": "b"},
        {"sku": "C81GS", "section": "Para-Military", "type": "Sprint Run", "src": "c"},
    ],
}


def make_image(path, size, color, mode="RGB"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, color).save(path)
    return path


class TempDirs(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for name, sub in (("IMAGES", "Catalogs/images"), ("DATA", "data"), ("CACHE", "cache"), ("FAMILIES", "families")):
            (self.tmp / sub).mkdir(parents=True)
            patcher = patch.object(paths, name, self.tmp / sub)
            patcher.start()
            self.addCleanup(patcher.stop)
        (paths.FAMILIES / "C81.json").write_text(json.dumps(FAMILY), encoding="utf-8")
        (paths.DATA / "dealers.json").write_text(json.dumps({"aliases": {}, "domains": {"Blade HQ": "bladehq.com"}}), encoding="utf-8")

    def img(self, name, size=(800, 600), color="white", mode="RGB"):
        return make_image(self.tmp / "src" / name, size, color, mode)


class TestAnalyse(TempDirs):
    def test_white_and_dark(self):
        self.assertEqual(images.analyse(self.img("w.jpg", (800, 400))), {"w": 800, "h": 400, "white": True, "ratio": 2.0})
        self.assertFalse(images.analyse(self.img("d.jpg", color="black"))["white"])

    def test_transparent_png_judged_white(self):
        self.assertTrue(images.analyse(self.img("t.png", color=(0, 0, 0, 0), mode="RGBA"))["white"])


class TestChoose(unittest.TestCase):
    def test_prefers_white_800_over_dark_2000(self):
        white = {"w": 800, "h": 600, "ratio": 1.33, "white": True, "md5": "a"}
        dark = {"w": 2000, "h": 1500, "ratio": 1.33, "white": False, "md5": "b"}
        self.assertIs(images.choose([dark, white]), white)

    def test_rejects_banner_and_small(self):
        banner = {"w": 1800, "h": 600, "ratio": 3.0, "white": True, "md5": "a"}
        small = {"w": 150, "h": 150, "ratio": 1.0, "white": True, "md5": "b"}
        self.assertIsNone(images.choose([banner, small]))

    def test_falls_back_to_largest(self):
        a = {"w": 300, "h": 300, "ratio": 1.0, "white": False, "md5": "a"}
        b = {"w": 500, "h": 500, "ratio": 1.0, "white": False, "md5": "b"}
        self.assertIs(images.choose([a, b]), b)


class TestChooseBlacklist(TempDirs):
    def test_skips_blacklisted_md5(self):
        (paths.DATA / "bad_md5.txt").write_text("bad\n", encoding="utf-8")
        self.assertIsNone(images.choose([{"w": 800, "h": 600, "ratio": 1.33, "white": True, "md5": "bad"}]))


class TestTargetName(TempDirs):
    def test_main_and_extra(self):
        self.assertEqual(images.target_name("C81", "C81GP", "jpg", False, b"x"), "images/C81/C81GP.jpg")
        self.assertEqual(images.target_name("C81", "C81GP", "jpg", True, b"x"), "images/C81/C81GP_2.jpg")

    def test_existing_path_gets_md5_suffix(self):
        make_image(paths.IMAGES / "C81" / "C81GP.jpg", (10, 10), "white")
        name = images.target_name("C81", "C81GP", "jpg", False, b"x")
        self.assertRegex(name, r"^images/C81/C81GP\.[0-9a-f]{6}\.jpg$")


class TestAccept(TempDirs):
    def test_accept_twice_without_replace_raises(self):
        images.accept("C81", "C81GP", self.img("a.jpg"))
        with self.assertRaises(ValueError):
            images.accept("C81", "C81GP", self.img("b.jpg", color="gray"))

    def test_replace_writes_new_path_and_removes_old(self):
        old = images.accept("C81", "C81GP", self.img("a.jpg"))
        new = images.accept("C81", "C81GP", self.img("b.jpg", color="gray"), replace=True)
        self.assertNotEqual(old, new)
        self.assertFalse((paths.IMAGES.parent / old).exists())
        self.assertTrue((paths.IMAGES.parent / new).exists())
        self.assertEqual(data.load_images()["C81GP"]["file"], new)

    def test_extra_appends(self):
        images.accept("C81", "C81GP", self.img("a.jpg"))
        extra = images.accept("C81", "C81GP", self.img("b.jpg", color="gray"), extra=True)
        self.assertEqual(extra, "images/C81/C81GP_2.jpg")
        self.assertEqual(data.load_images()["C81GP"]["extra"], [extra])

    def test_blacklisted_rejected(self):
        f = self.img("a.jpg")
        images.reject(f)
        with self.assertRaises(ValueError):
            images.accept("C81", "C81GP", f)
        self.assertEqual(data.load_images(), {})

    def test_unknown_sku_rejected(self):
        with self.assertRaises(ValueError):
            images.accept("C81", "C999", self.img("a.jpg"))


class TestPatterns(unittest.TestCase):
    def test_key_pattern_word_bounded(self):
        rx = re.compile(images.key_pattern(["C81GP"]), re.I)
        self.assertTrue(rx.search("Spyderco C81GP Para-Military"))
        self.assertTrue(rx.search("model 81GP plain"))
        self.assertTrue(rx.search("/files/C81GPBoth.jpg"))
        self.assertFalse(rx.search("Spyderco C81GPBK2"))

    def test_junk_and_search(self):
        self.assertRegex("https://x.com/img/coming-soon.jpg", images.JUNK_RE)
        self.assertNotRegex("https://x.com/img/c81gp.jpg", images.JUNK_RE)
        self.assertRegex("https://x.com/search?q=c81gp", images.SEARCH_RE)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestGalleryHelperPure(unittest.TestCase):
    """Pure functions of browser/gallery.mjs, and the Python regexes compiled by JS; no browser."""

    def node(self, script):
        proc = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                              cwd=paths.TOOLS / "browser")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_filters_and_patterns(self):
        out = self.node(
            "import { full, bestCandidates } from './gallery.mjs';"
            f"const junk = new RegExp({json.dumps(images.JUNK_RE)}, 'i');"
            f"const key = new RegExp({json.dumps(images.key_pattern(['C81GP']))}, 'i');"
            "console.log(JSON.stringify({"
            " full: full('https://cdn.x.com/files/C81GP_600x600.jpg?v=3&width=200'),"
            " best: bestCandidates(['https://x/logo.png', 'https://x/C81GP-300x300.jpg', 'https://x/C81GP.jpg'], junk),"
            " key: [key.test('Spyderco C81GP'), key.test('Spyderco C81GPBK2')]}));"
        )
        self.assertEqual(out, {"full": "https://cdn.x.com/files/C81GP.jpg?v=3", "best": ["https://x/C81GP.jpg"], "key": [True, False]})


class TestCandidates(TempDirs):
    def test_sources(self):
        paths.CACHE.joinpath("official.json").write_text(json.dumps([{
            "title": "PM", "handle": "pm", "published": "", "skus": ["C81GP", "C81GPBK2"],
            "images": ["https://cdn/x/C81GPBK2_Both.jpg", "https://cdn/x/C81GP_Both.jpg?v=1", "https://cdn/x/C81GP_open.jpg"],
        }]), encoding="utf-8")
        paths.CACHE.joinpath("sitemaps.json").write_text(json.dumps({
            "bladehq.com": ["https://bladehq.com/spyderco-c81gpbk2-pm2", "https://bladehq.com/other"],
            "knifecenter.com": ["https://knifecenter.com/item/C81GP", "https://knifecenter.com/item/C81GPX-alt", "https://knifecenter.com/item/C81GPBK2"],
        }), encoding="utf-8")
        make_image(paths.IMAGES / "C81" / "C81GS.jpg", (10, 10), "white")
        data.save_images({"C81GS": {"file": "images/C81/C81GS.jpg", "extra": []}})

        out = images.candidates("C81", add=["C81GP=https://example.com/c81gp"])
        saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertNotIn("C81GS", saved)
        gp = [c["url"] for c in saved["C81GP"]["candidates"]]
        self.assertEqual(gp, [
            "https://cdn/x/C81GP_Both.jpg?v=1",
            "https://knifecenter.com/item/C81GP",
            "https://knifecenter.com/item/C81GPX-alt",
            "https://example.com/c81gp",
        ])
        bk = saved["C81GPBK2"]["candidates"]
        self.assertEqual([c["source"] for c in bk], ["official", "dealer", "sitemap"])
        self.assertEqual(bk[1]["url"], "https://bladehq.com/spyderco-c81gpbk2-pm2")

    def test_rerun_keeps_status(self):
        images.candidates("C81", skus=["C81GP"], add=["C81GP=https://example.com/a"])
        path = paths.CACHE / "candidates" / "C81.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved["C81GP"]["candidates"][0]["status"] = "none"
        path.write_text(json.dumps(saved), encoding="utf-8")
        images.candidates("C81", skus=["C81GP"], add=["C81GP=https://example.com/b"])
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([(c["url"], c["status"]) for c in saved["C81GP"]["candidates"]],
                         [("https://example.com/a", "none"), ("https://example.com/b", "pending")])

    def test_bad_add(self):
        with self.assertRaises(ValueError):
            images.candidates("C81", add=["nourl"])


def helper_cmd(response):
    code = f"import json,sys; job=json.load(open(sys.argv[1])); json.dump({response!r}, open(job['result'], 'w'))"
    return [sys.executable, "-c", code]


class TestFetch(TempDirs):
    def write_candidates(self, cands):
        path = paths.CACHE / "candidates" / "C81.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(cands), encoding="utf-8")
        return path

    def test_verified_accepted_unverified_reviewed_photo_skus_untouched(self):
        make_image(paths.IMAGES / "C81" / "C81GS.jpg", (10, 10), "white")
        data.save_images({"C81GS": {"file": "images/C81/C81GS.jpg", "extra": []}})
        cand = lambda url: {"url": url, "page": url, "source": "add", "status": "pending"}
        path = self.write_candidates({
            "C81GP": {"aliases": [], "candidates": [cand("https://a.com/c81gp")]},
            "C81GPBK2": {"aliases": [], "candidates": [cand("https://b.com/x"), cand("https://b.com/search?q=1")]},
            "C81GS": {"aliases": [], "candidates": [cand("https://c.com/c81gs")]},
        })
        good = str(self.img("good.jpg"))
        other = str(self.img("other.jpg", color="gray"))
        response = {"results": [
            {"sku": "C81GP", "url": "https://a.com/c81gp", "page": "https://a.com/c81gp", "status": "ok", "verified": True,
             "images": [{"path": good, "url": "https://a.com/i/c81gp.jpg"}]},
            {"sku": "C81GPBK2", "url": "https://b.com/x", "page": "https://b.com/x", "status": "ok", "verified": False,
             "images": [{"path": other, "url": "https://b.com/i/x.jpg"}]},
        ], "stopped": None}

        captured = {}
        real_run = images.sources.run_helper

        def spy(script, job, cmd=None):
            captured["job"] = job
            return real_run(script, job, cmd=helper_cmd(response))

        with patch.object(images.sources, "run_helper", spy):
            images.fetch("C81")

        self.assertEqual({i["sku"] for i in captured["job"]["items"]}, {"C81GP", "C81GPBK2"})
        self.assertEqual(captured["job"]["items"][1]["urls"], ["https://b.com/x"])
        recs = data.load_images()
        self.assertEqual(recs["C81GP"]["file"], "images/C81/C81GP.jpg")
        self.assertEqual(recs["C81GP"]["page"], "https://a.com/c81gp")
        self.assertNotIn("C81GPBK2", recs)
        self.assertEqual(recs["C81GS"], {"file": "images/C81/C81GS.jpg", "extra": []})
        review = json.loads((paths.CACHE / "review" / "review.json").read_text(encoding="utf-8"))
        (name, entry), = review.items()
        self.assertEqual(entry["sku"], "C81GPBK2")
        self.assertTrue((paths.CACHE / "review" / name).exists())
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(saved["C81GP"]["done"])
        self.assertEqual([c["status"] for c in saved["C81GPBK2"]["candidates"]], ["review", "search"])

        # accepting a review file picks up its page/url metadata
        images.accept("C81", "C81GPBK2", paths.CACHE / "review" / name)
        self.assertEqual(data.load_images()["C81GPBK2"]["page"], "https://b.com/x")

    def test_shared_url_per_sku_and_bad_image_recorded_as_error(self):
        url = "https://shared.com/p"
        cand = {"url": url, "page": url, "source": "add", "status": "pending"}
        path = self.write_candidates({"C81GP": {"aliases": [], "candidates": [dict(cand)]},
                                      "C81GPBK2": {"aliases": [], "candidates": [dict(cand)]}})
        gif, good = str(self.img("bad.gif")), str(self.img("good.jpg"))
        response = {"results": [
            {"sku": "C81GP", "url": url, "page": url, "status": "ok", "verified": True,
             "images": [{"path": gif, "url": "https://shared.com/i/c81gp.gif"}]},
            {"sku": "C81GPBK2", "url": url, "page": url, "status": "ok", "verified": True,
             "images": [{"path": good, "url": "https://shared.com/i/c81gpbk2.jpg"}]},
        ], "stopped": None}
        real_run = images.sources.run_helper
        with patch.object(images.sources, "run_helper", lambda s, j, cmd=None: real_run(s, j, cmd=helper_cmd(response))):
            summary = images.fetch("C81")

        self.assertEqual(summary["accepted"], ["C81GPBK2"])
        saved = json.loads(path.read_text(encoding="utf-8"))
        gp = saved["C81GP"]["candidates"][0]
        self.assertEqual(gp["status"], "error")
        self.assertIn("GIF", gp["error"])
        self.assertEqual(saved["C81GPBK2"]["candidates"][0]["status"], "accepted")
        self.assertNotIn("C81GP", data.load_images())


class TestSheet(TempDirs):
    def test_all_mode_numbers_files(self):
        images.accept("C81", "C81GP", self.img("a.jpg"))
        images.accept("C81", "C81GS", self.img("b.jpg", color="gray"))
        sheets = images.sheet("C81", "all")
        self.assertEqual(len(sheets), 1)
        self.assertTrue(sheets[0].exists())
        index = json.loads((paths.CACHE / "sheets" / "C81-all.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(Path(f).name for f in index.values()), ["C81GP.jpg", "C81GS.jpg"])


if __name__ == "__main__":
    unittest.main()
