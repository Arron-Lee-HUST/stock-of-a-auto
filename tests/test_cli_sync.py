import csv
import tempfile
import unittest
from pathlib import Path

from stock_auto.cli import _upsert_daily_bars
from stock_auto.data import DailyBar


class CliSyncTests(unittest.TestCase):
    def test_daily_csv_upsert_replaces_existing_key_and_keeps_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily.csv"
            path.write_text(
                "symbol,trade_date,open,high,low,close,volume,amount,prev_close,is_suspended,limit_pct\n"
                "sh600000,2026-11-10,10,11,9,10.5,1000,10000,10,false,0.1\n",
                encoding="utf-8",
            )
            bars = [
                DailyBar("sh600000", "2026-11-10", 10, 12, 9, 11, 1200, 13200, 10),
                DailyBar("sh600000", "2026-11-11", 11, 12, 10, 11.5, 1500, 17250, 11),
            ]
            count = _upsert_daily_bars(path, bars)
            with path.open("r", encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(count, 2)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["close"], "11")
            self.assertEqual(rows[1]["trade_date"], "2026-11-11")


if __name__ == "__main__":
    unittest.main()
