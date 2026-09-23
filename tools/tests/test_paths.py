import unittest

import spy
from lib import paths


class TestPaths(unittest.TestCase):
    def test_root_contains_catalogs(self):
        self.assertTrue((paths.ROOT / "Catalogs").exists())

    def test_tools_name(self):
        self.assertEqual(paths.TOOLS.name, "tools")


class TestSpyCli(unittest.TestCase):
    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as cm:
            spy.main(["--help"])
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
