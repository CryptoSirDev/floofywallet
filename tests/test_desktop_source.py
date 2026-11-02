"""Desktop source syntax smoke test; does not require a GUI on CI."""
import ast
from pathlib import Path
import unittest


class DesktopSourceTests(unittest.TestCase):
    def test_desktop_module_parses(self):
        source = (Path(__file__).resolve().parents[1] / "floofywallet" / "desktop.py").read_text(encoding="utf-8")
        ast.parse(source, filename="desktop.py")


if __name__ == "__main__":
    unittest.main()
