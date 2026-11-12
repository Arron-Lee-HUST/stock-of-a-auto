import unittest

from stock_auto.akshare_provider import AkshareMarketDataProvider


class FakeAk:
    def stock_zh_a_hist(self, **kwargs):
        self.hist_args = kwargs
        return [
            {"日期": "2024-01-02", "开盘": 10, "收盘": 11, "最高": 11, "最低": 9.8, "成交量": 100, "成交额": 110000},
            {"日期": "2024-01-03", "开盘": 11, "收盘": 12, "最高": 12, "最低": 10.8, "成交量": 200, "成交额": 240000},
        ]

    def stock_zh_a_spot_em(self):
        return [
            {"代码": "600000", "名称": "浦发银行", "最新价": 10.2, "涨跌幅": 1.5, "成交量": 1000, "成交额": 1000000},
            {"代码": "000001", "名称": "平安银行", "最新价": 11.2, "涨跌幅": -0.5, "成交量": 2000, "成交额": 2000000},
        ]


class AkshareProviderTests(unittest.TestCase):
    def test_daily_bars_are_normalized_and_unadjusted(self):
        fake = FakeAk()
        bars = AkshareMarketDataProvider(fake).get_bars(["sh600000"], "2024-01-01", "2024-01-31")
        self.assertEqual(fake.hist_args["adjust"], "")
        self.assertEqual([bar.trade_date for bar in bars], ["2024-01-02", "2024-01-03"])
        self.assertEqual(bars[0].volume, 10000)
        self.assertEqual(bars[1].prev_close, 11)
        self.assertEqual(bars[0].amount, 110000)

    def test_spot_quotes_filter_symbols_and_mark_capture_source(self):
        quotes = AkshareMarketDataProvider(FakeAk()).get_spot_quotes(["sh600000"])
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["symbol"], "sh600000")
        self.assertEqual(quotes[0]["volume_shares"], 100000)
        self.assertEqual(quotes[0]["source"], "akshare.stock_zh_a_spot_em")
        self.assertTrue(quotes[0]["captured_at"])


if __name__ == "__main__":
    unittest.main()
