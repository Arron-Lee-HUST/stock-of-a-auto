import tempfile
import unittest
from pathlib import Path

from stock_auto.backtest import BacktestConfig, BacktestEngine
from stock_auto.data import CsvMarketDataProvider, DailyBar


class DataProviderTests(unittest.TestCase):
    def test_csv_provider_filters_and_sorts(self):
        content = "symbol,trade_date,open,high,low,close,volume\nsh600000,2024-01-02,10,11,9,10.5,1000\nsh600000,2024-01-03,10.5,11,10,10.8,1200\nsz000001,2024-01-02,8,9,7,8.5,900\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bars.csv"
            path.write_text(content, encoding="utf-8")
            bars = CsvMarketDataProvider(path).get_bars(["sh600000"], "2024-01-02", "2024-01-03")
        self.assertEqual([b.trade_date for b in bars], ["2024-01-02", "2024-01-03"])


class BacktestTests(unittest.TestCase):
    def test_next_open_execution_and_t1_exit(self):
        bars = [
            DailyBar("sh600000", "2024-01-02", 10, 10.5, 9.8, 10.2, 10000, prev_close=10),
            DailyBar("sh600000", "2024-01-03", 10.2, 10.8, 10.1, 10.7, 10000, prev_close=10.2),
            DailyBar("sh600000", "2024-01-04", 10.8, 11, 10.5, 10.9, 10000, prev_close=10.7),
        ]
        engine = BacktestEngine(BacktestConfig(initial_cash=100000, commission_rate=0, stamp_duty_rate=0,
                                               slippage_rate=0, min_commission=0, max_single_position_pct=0.5))
        result = engine.run(
            bars,
            entry_selector=lambda date, history: ["sh600000"] if date == "2024-01-02" else [],
            exit_selector=lambda date, position, history: date == "2024-01-03",
        )
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].entry_date, "2024-01-03")
        self.assertEqual(result.trades[0].exit_date, "2024-01-04")

    def test_limit_up_entry_is_rejected(self):
        bars = [
            DailyBar("sh600000", "2024-01-02", 10, 10.2, 9.9, 10, 10000, prev_close=10),
            DailyBar("sh600000", "2024-01-03", 11, 11, 11, 11, 10000, prev_close=10, limit_pct=0.10),
        ]
        engine = BacktestEngine(BacktestConfig(initial_cash=100000, commission_rate=0, min_commission=0,
                                               slippage_rate=0))
        result = engine.run(bars, lambda date, history: ["sh600000"], lambda *args: False)
        self.assertTrue(any("limit-up" in item for item in result.rejected_orders))
        self.assertEqual(result.trades, [])


if __name__ == "__main__":
    unittest.main()
