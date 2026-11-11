import unittest

from stock_auto.providers import TushareMarketDataProvider, normalize_symbol, to_tushare_symbol


class FakeFrame:
    def to_dict(self, orient):
        assert orient == "records"
        return [{
            "ts_code": "600000.SH", "trade_date": "20240103",
            "open": 10, "high": 11, "low": 9.8, "close": 10.5,
            "vol": 1000, "amount": 12000, "pre_close": 10,
        }]


class FakePro:
    def daily(self, **kwargs):
        self.kwargs = kwargs
        return FakeFrame()


class ProviderTests(unittest.TestCase):
    def test_symbol_conversion(self):
        self.assertEqual(normalize_symbol("600000.SH"), "sh600000")
        self.assertEqual(normalize_symbol("sz000001"), "sz000001")
        self.assertEqual(to_tushare_symbol("sh600000"), "600000.SH")

    def test_tushare_daily_conversion(self):
        client = FakePro()
        bars = TushareMarketDataProvider(client).get_bars(["sh600000"], "2024-01-01", "2024-01-31")
        self.assertEqual(client.kwargs["start_date"], "20240101")
        self.assertEqual(bars[0].symbol, "sh600000")
        self.assertEqual(bars[0].volume, 100000)
        self.assertEqual(bars[0].amount, 12000000)
        self.assertEqual(bars[0].prev_close, 10)


if __name__ == "__main__":
    unittest.main()
