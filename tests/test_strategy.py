import unittest

from stock_auto import (
    MarketSnapshot, StrategyConfig, TradePosition, assess_market_risk,
    calculate_position_size, evaluate_entry, evaluate_exit, evaluate_candidate,
)


class StrategyTests(unittest.TestCase):
    def candidate(self, **overrides):
        values = dict(
            symbol="sh600000", close=10.8, prev_close=10.3, pct_change=4.85,
            ma5=10.5, ma10=10.2, ma20=9.9, volume=1800, avg_volume_5=1000,
            main_net_inflow=1200000, recent_limit_up=True, prior_high=10.6,
            sector_rank=3, sector_limit_up_count=4, sector_leader_limit_up=True,
            catalyst=True,
        )
        values.update(overrides)
        return MarketSnapshot(**values)

    def test_strong_candidate_passes(self):
        signal = evaluate_candidate(self.candidate())
        self.assertTrue(signal.eligible)
        self.assertGreaterEqual(signal.score, 60)
        self.assertEqual(signal.symbol, "sh600000")

    def test_missing_required_volume_does_not_pass(self):
        signal = evaluate_candidate(self.candidate(volume=None))
        self.assertFalse(signal.eligible)
        self.assertIn("volume", signal.missing_fields)

    def test_weak_trend_is_rejected(self):
        signal = evaluate_candidate(self.candidate(close=9.8))
        self.assertFalse(signal.eligible)

    def test_entry_waits_without_auction_data(self):
        snapshot = self.candidate()
        signal = evaluate_candidate(snapshot)
        decision = evaluate_entry(snapshot, signal)
        self.assertEqual(decision.action, "wait")

    def test_entry_buy_after_confirmation(self):
        snapshot = self.candidate(
            auction_pct=1.5, auction_volume_ratio=1.8, price=10.9,
            vwap=10.7, intraday_volume_ratio=1.3,
            auction_source_timestamp="2026-11-12T09:26:00+08:00",
            quote_source_timestamp="2026-11-12T09:31:00+08:00",
            order_book_source_timestamp="2026-11-12T09:31:00+08:00",
            order_book_complete=True, order_book_imbalance=0.1,
            bid_depth_shares=10000, ask_depth_shares=9000,
        )
        decision = evaluate_entry(snapshot, evaluate_candidate(snapshot))
        self.assertEqual(decision.action, "buy")

    def test_stop_loss(self):
        decision = evaluate_exit(
            MarketSnapshot(symbol="x", price=9.5),
            TradePosition(symbol="x", entry_price=10, quantity=100),
        )
        self.assertEqual(decision.action, "sell")

    def test_risk_off_and_position_size(self):
        cfg = StrategyConfig()
        risk = assess_market_risk(MarketSnapshot(
            symbol="market", market_limit_up_count=10,
            market_limit_down_count=30, market_max_streak=1,
        ), cfg)
        self.assertEqual(risk.level, "risk_off")
        self.assertEqual(calculate_position_size(100000, 100000, 10, 0, risk, cfg), 0)


if __name__ == "__main__":
    unittest.main()
