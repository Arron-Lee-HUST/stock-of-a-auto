import unittest

from stock_auto.backtest import BacktestConfig
from stock_auto.context import AuctionQuote, CapitalFlow, IntradayQuote, SectorContext
from stock_auto.data import DailyBar
from stock_auto.strategy_backtest import ThreeDriveBacktest


class Context:
    def get_auction_quotes(self, symbols, date):
        return [AuctionQuote(s, date, 2.0, 2.0) for s in symbols]
    def get_intraday_quotes(self, symbols, date):
        return [IntradayQuote(s, date, 10.0, 9.9, 1.5) for s in symbols]
    def get_capital_flows(self, symbols, date):
        return [CapitalFlow(s, date, 100000) for s in symbols]
    def get_sector_context(self, symbols, date):
        return [SectorContext(s, date, 1, 3, True, True) for s in symbols]


class StrategyBacktestTests(unittest.TestCase):
    def test_runner_uses_context_factory_and_executes_orders(self):
        bars = []
        close = 10.0
        for day in range(1, 27):
            prev = close
            close = prev * (1.025 if day == 25 else 1.01)
            bars.append(DailyBar("sh600000", f"2024-01-{day:02d}",
                                 prev * 1.005, close, prev * 0.995, close,
                                 2000 + day * 100, prev_close=prev))
        cfg = BacktestConfig(initial_cash=100000, commission_rate=0, stamp_duty_rate=0,
                             slippage_rate=0, min_commission=0, max_single_position_pct=0.5)
        result = ThreeDriveBacktest(backtest_config=cfg).run(
            bars, context_factory=lambda date: Context()
        )
        self.assertGreater(len(result.equity_curve), 0)
        self.assertGreaterEqual(result.final_equity, 0)


if __name__ == "__main__":
    unittest.main()
