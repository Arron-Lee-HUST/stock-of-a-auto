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

    def test_stale_snapshot_is_skipped(self):
        snapshot = MarketSnapshot("sh600000", trade_date="2024-01-01")
        market = MarketSnapshot("market", market_limit_up_count=50,
                                market_limit_down_count=2, market_max_streak=5)
        report = MarketMonitor().evaluate("2024-01-02", "09:31:00",
            {"sh600000": snapshot}, {}, {}, market)
        self.assertEqual(report.events[0].action, "skip")

    def test_outside_session_does_not_emit_trade_action(self):
        market = MarketSnapshot("market", market_limit_up_count=50,
                                market_limit_down_count=2, market_max_streak=5)
        report = MarketMonitor().evaluate("2024-01-02", "16:00:00", {}, {}, {}, market)
        self.assertEqual(report.events[0].phase, "outside_session")


if __name__ == "__main__":
    unittest.main()
