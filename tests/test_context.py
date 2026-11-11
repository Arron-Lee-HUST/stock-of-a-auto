import tempfile
import unittest
from pathlib import Path

from stock_auto.context import CsvPointInTimeContextProvider


class ContextProviderTests(unittest.TestCase):
    def test_only_requested_date_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flow.csv"
            path.write_text("symbol,trade_date,main_net_inflow\nsh600000,2024-01-02,100\nsh600000,2024-01-03,999\n", encoding="utf-8")
            provider = CsvPointInTimeContextProvider(flow_path=path)
            rows = provider.get_capital_flows(["sh600000"], "2024-01-02")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].main_net_inflow, 100)


if __name__ == "__main__":
    unittest.main()
