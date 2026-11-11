import unittest

from stock_auto.backtest import BacktestConfig
from stock_auto.data import DailyBar
from stock_auto.paper import PaperBroker


class PaperBrokerTests(unittest.TestCase):
    def setUp(self):
        self.broker = PaperBroker(100000, BacktestConfig(
            initial_cash=100000, commission_rate=0, stamp_duty_rate=0,
            slippage_rate=0, min_commission=0,
        ))

    def test_buy_executes_next_day_and_sell_obeys_t1(self):
        order = self.broker.submit_order("b1", "sh600000", "BUY", 100, "2024-01-02")
        self.assertEqual(order.status, "pending")
        fills = self.broker.process_bar(DailyBar("sh600000", "2024-01-03",
            10, 10.5, 9.9, 10.2, 10000, prev_close=10))
        self.assertEqual(fills[0].side, "BUY")
        sell = self.broker.submit_order("s1", "sh600000", "SELL", 100, "2024-01-03")
        self.broker.process_bar(DailyBar("sh600000", "2024-01-03",
            10.2, 10.5, 10, 10.3, 10000, prev_close=10))
        self.assertEqual(sell.status, "pending")
        fills = self.broker.process_bar(DailyBar("sh600000", "2024-01-04",
            10.4, 10.8, 10.2, 10.6, 10000, prev_close=10.3))
        self.assertEqual(fills[0].side, "SELL")
        self.assertNotIn("sh600000", self.broker.account.positions)

    def test_missing_previous_close_blocks_fill(self):
        order = self.broker.submit_order("b-missing", "sh600000", "BUY", 100, "2024-01-02")
        self.broker.process_bar(DailyBar("sh600000", "2024-01-03", 10, 10.5, 9.9, 10.2, 10000))
        self.assertEqual(order.status, "rejected")
        self.assertIn("missing_prev_close", order.reason)

    def test_duplicate_order_id_is_idempotent(self):
        first = self.broker.submit_order("same", "sh600000", "BUY", 100, "2024-01-02")
        second = self.broker.submit_order("same", "sh600000", "BUY", 200, "2024-01-02")
        self.assertIs(first, second)
        self.assertEqual(second.quantity, 100)


if __name__ == "__main__":
    unittest.main()
