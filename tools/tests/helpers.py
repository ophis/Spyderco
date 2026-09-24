import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import catalog, paths

FIXTURES = Path(__file__).resolve().parent / "fixtures"
README = "# Repo\n\n<!-- families:start -->\n<!-- families:end -->\n"


class TempRepo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for name, rel in (("CATALOGS", "Catalogs"), ("IMAGES", "Catalogs/images"),
                          ("CACHE", "tools/cache"), ("DATA", "tools/data")):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
            self._patch(name, self.root / rel)
        self._patch("README", self.root / "README.md")
        paths.README.write_text(README, encoding="utf-8")

    def _patch(self, name, value):
        p = patch.object(paths, name, value)
        p.start()
        self.addCleanup(p.stop)

    def write_wiki(self, page, text):
        path = paths.CACHE / "wiki" / f"{page}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def quiet(self, fn, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = fn(*args, **kwargs)
        self.output = out.getvalue()
        return result


def make_catalog(id_, file, sections, rows, **config):
    cfg = {"id": id_, "wiki_page": file.replace(" ", "_"), "readme_label": file, "section_rules": [],
           "aliases": {}, "skip": [], "manual": [], "wiki_errors": {}, **config}
    cat = catalog.Catalog(paths.CATALOGS / f"{file}.md", file, ["Preamble.", ""], list(sections), list(rows), cfg)
    catalog.save(cat)
    return cat
