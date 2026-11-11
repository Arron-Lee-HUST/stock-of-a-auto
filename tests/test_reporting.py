import tempfile
import unittest
from pathlib import Path

from stock_auto.reporting import _plain, write_dashboard, write_json


class ReportingTests(unittest.TestCase):
    def test_dashboard_escapes_untrusted_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_dashboard(Path(tmp) / "index.html", "报告",
                                   {"股票": "<script>alert(1)</script>"},
                                   [{"symbol": "<img src=x>"}])
            content = path.read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", content)
        self.assertIn("&lt;script&gt;", content)
        self.assertIn("&lt;img", content)

    def test_non_finite_metrics_become_json_null(self):
        import math
        self.assertIsNone(_plain(math.inf))
        self.assertIsNone(_plain(math.nan))

    def test_json_writes_nested_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_json(Path(tmp) / "a.json", {"value": 1})
            self.assertIn('"value": 1', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
