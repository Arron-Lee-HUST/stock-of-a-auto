import unittest

from stock_auto.models import MarketSnapshot, Signal, TradePosition
from stock_auto.monitor import MarketMonitor


class MonitorTests(unittest.TestCase):
    def test_auction_pass_is_watch_not_buy(self):
        snapshot = MarketSnapshot("sh600000", trade_date="2024-01-02", auction_pct=2,
                                  auction_volume_ratio=1.5)
        signal = Signal("sh600000", 80, 30, 25, 25, True)
        market = MarketSnapshot("market", market_limit_up_count=50,
                                market_limit_down_count=2, market_max_streak=5)
        report = MarketMonitor().evaluate("2024-01-02", "09:23:00",
            {"sh600000": snapshot}, {"sh600000": signal}, {}, market)
        self.assertEqual(report.events[0].action, "watch")


    def test_missing_order_book_blocks_intraday_entry(self):
        snapshot = MarketSnapshot("sh600000", trade_date="2024-01-02", price=10.2,
                                  vwap=10.0, auction_pct=2, auction_volume_ratio=1.5,
                                  intraday_volume_ratio=1.2,
                                  quote_source_timestamp="2024-01-02T09:31:00+08:00",
                                  order_book_source_timestamp="2024-01-02T09:31:00+08:00")
        signal = Signal("sh600000", 80, 30, 25, 25, True)
        market = MarketSnapshot("market", market_limit_up_count=50,
                                market_limit_down_count=2, market_max_streak=5)
        report = MarketMonitor().evaluate("2024-01-02", "09:31:00",
            {"sh600000": snapshot}, {"sh600000": signal}, {}, market)
        self.assertEqual(report.events[0].action, "wait")
        self.assertIn("五档盘口数据不完整", report.events[0].reasons[0])

    def test_stale_snapshot_is_skipped(self):
        snapshot = MarketSnapshot("sh600000", trade_date="2024-01-01")
        market = MarketSnapshot("market", market_limit_up_count=50,
                                market_limit_down_count=2, market_max_streak=5)
        report = MarketMonitor().evaluate("2024-01-02", "09:31:00",
            {"sh600000": snapshot}, {}, {}, market)
        self.assertEqual(report.events[0].action, "skip")

    def test_risk_off_blocks_new_entries(self):
        snapshot = MarketSnapshot("sh600000", trade_date="2024-01-02", price=10.2, vwap=10.0,
                                  auction_pct=2, auction_volume_ratio=2, intraday_volume_ratio=1.5)
        signal = Signal("sh600000", 80, 30, 25, 25, True)
        market = MarketSnapshot("market", market_limit_up_count=5,
                                market_limit_down_count=30, market_max_streak=1)
        report = MarketMonitor().evaluate("2024-01-02", "09:31:00",
            {"sh600000": snapshot}, {"sh600000": signal}, {}, market)
        self.assertEqual(report.events[0].action, "no_new_entries")

    def test_auction_phase_does_not_use_previous_close_for_exit(self):
        snapshot = MarketSnapshot("sh600000", trade_date="2024-01-02", close=8.0)
        position = TradePosition("sh600000", 10.0, 100, entry_date="2024-01-01")
        market = MarketSnapshot("market", market_limit_up_count=50,
                                market_limit_down_count=2, market_max_streak=5)
        report = MarketMonitor().evaluate("2024-01-02", "09:23:00",
            {"sh600000": snapshot}, {}, {"sh600000": position}, market)
        self.assertEqual(report.events[0].action, "hold")

    def test_t1_blocks_same_day_exit_signal(self):
        snapshot = MarketSnapshot("sh600000", trade_date="2024-01-02", close=9.0, price=9.0)
        position = TradePosition("sh600000", 10.0, 100, entry_date="2024-01-02")
        market = MarketSnapshot("market", market_limit_up_count=50,
                                market_limit_down_count=2, market_max_streak=5)
        report = MarketMonitor().evaluate("2024-01-02", "10:00:00",
            {"sh600000": snapshot}, {}, {"sh600000": position}, market)
        self.assertEqual(report.events[0].action, "hold")

    def test_outside_session_does_not_emit_trade_action(self):
        market = MarketSnapshot("market", market_limit_up_count=50,
                                market_limit_down_count=2, market_max_streak=5)
        report = MarketMonitor().evaluate("2024-01-02", "16:00:00", {}, {}, {}, market)
        self.assertEqual(report.events[0].phase, "outside_session")


if __name__ == "__main__":
    unittest.main()
