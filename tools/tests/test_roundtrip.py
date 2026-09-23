import unittest

from lib import data, paths, render


def _ids():
    if not (paths.FAMILIES / "_order.json").exists():
        return []
    return data.all_family_ids()


@unittest.skipUnless(_ids(), "families/ is empty; run `spy.py seed-from-md` first")
class TestRoundTrip(unittest.TestCase):
    def test_catalogs_byte_equal(self):
        images = data.load_images()
        for id_ in _ids():
            fam = data.load_family(id_)
            with self.subTest(family=id_):
                expected = (paths.CATALOGS / f"{fam['file']}.md").read_bytes()
                self.assertEqual(render.render_family(fam, images).encode("utf-8"), expected)

    def test_readme_table(self):
        text = paths.README.read_text(encoding="utf-8")
        start = text.index(render.FAMILIES_START) + len(render.FAMILIES_START)
        end = text.index(render.FAMILIES_END)
        families = [data.load_family(i) for i in _ids()]
        self.assertEqual(text[start:end], f"\n{render.render_readme_table(families)}\n")
