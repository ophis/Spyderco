import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lib import fsio

TOOLS = Path(__file__).resolve().parents[1]


class TestAtomicWrite(unittest.TestCase):
    def test_writes_text_and_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "out.txt"
            fsio.atomic_write(p, "hello")
            self.assertEqual(p.read_text(encoding="utf-8"), "hello")
            fsio.atomic_write(p, b"bytes")
            self.assertEqual(p.read_bytes(), b"bytes")

    def test_dump_json(self):
        self.assertEqual(fsio.dump_json({"a": "é"}), '{\n "a": "é"\n}\n')


class TestNoPillowAtLoad(unittest.TestCase):
    def test_cli_loads_without_pillow(self):
        code = (f"import sys; sys.modules['PIL'] = None; sys.path.insert(0, {str(TOOLS)!r}); "
                "import spy; spy.build_parser()")
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
