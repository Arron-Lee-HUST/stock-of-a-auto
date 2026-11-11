import unittest

from stock_auto.data import DailyBar
from stock_auto.scanner import CandidateScanner, build_snapshot


def history(symbol="sh600000"):
    values = []
    for i in range(1, 23):
        close = 10 + i * 0.1
        values.append(DailyBar(symbol, f"2024-01-{i:02d}", close, close * 1.01,
                               close * 0.99, close, 1000 + i * 100,
                               prev_close=close - 0.1))
    return values


class ScannerTests(unittest.TestCase):
    def test_snapshot_uses_only_data_up_to_date(self):
        bars = history()
        snap = build_snapshot(bars[:21])
        self.assertEqual(snap.trade_date, "2024-01-21")
        self.assertIsNotNone(snap.ma20)
        self.assertEqual(snap.avg_volume_5, sum(x.volume for x in bars[15:20]) / 5)
        self.assertEqual(snap.prior_high, max(x.high for x in bars[:20]))

    def test_scanner_does_not_treat_missing_context_as_pass(self):
        result = CandidateScanner().scan(history(), "2024-01-22")
        self.assertEqual(len(result.candidates), 0)
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("main_net_inflow", result.rejected[0].signal.missing_fields)

    def test_future_bars_are_ignored(self):
        bars = history()
        bars.append(DailyBar("sh600000", "2024-01-23", 20, 21, 19, 20, 10000, prev_close=11))
        result = CandidateScanner().scan(bars, "2024-01-22")
        self.assertEqual(result.rejected[0].snapshot.trade_date, "2024-01-22")


if __name__ == "__main__":
    unittest.main()
