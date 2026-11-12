import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from stock_auto.auction_history import AuctionHistoryStore
from stock_auto.realtime_provider import EastmoneyTencentRealtimeProvider


class RealtimeProviderTests(unittest.TestCase):
    def test_auction_uses_final_0926_row_and_previous_auction_volume_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = AuctionHistoryStore(Path(tmp) / "auction.sqlite3")
            history.record("sh600000", "2026-11-11", 50000)

            def transport(url, headers, timeout):
                if "trends2/get" in url:
                    return {"data": {"trends": [
                        "2026-11-12 09:15,10.1,10.1,10.1,10.1,0,0,0",
                        "2026-11-12 09:26,10.5,10.6,10.6,10.5,1000,1060000,0",
                    ]}}
                raise AssertionError(url)

            provider = EastmoneyTencentRealtimeProvider(
                transport=transport, min_interval_seconds=0,
                auction_db_path=str(Path(tmp) / "auction.sqlite3"))
            result = provider.get_auction_observations(["sh600000"], "2026-11-12")
            auction = result["sh600000"]
            self.assertEqual(auction["logical_auction_time"], "09:25")
            self.assertEqual(auction["auction_price"], 10.6)
            self.assertEqual(auction["auction_volume_shares"], 100000)
            self.assertAlmostEqual(auction["auction_volume_ratio"], 2.0)

    def test_order_book_maps_eastmoney_five_levels_and_imbalance(self):
        def transport(url, headers, timeout):
            return {"data": {
                "f19": "10.00", "f20": "100", "f17": "9.99", "f18": "200",
                "f39": "10.01", "f40": "150", "f37": "10.02", "f38": "250",
            }}

        with tempfile.TemporaryDirectory() as tmp:
            provider = EastmoneyTencentRealtimeProvider(
                transport=transport, min_interval_seconds=0,
                auction_db_path=str(Path(tmp) / "auction.sqlite3"))
            book = provider.get_order_books(["sh600000"])["sh600000"]
            self.assertEqual(book["bids"][0]["price"], 10.0)
            self.assertEqual(book["bids"][0]["volume_shares"], 10000)
            self.assertEqual(book["asks"][0]["volume_shares"], 15000)
            self.assertAlmostEqual(book["book_imbalance"], -1 / 7)



    def test_market_stats_uses_limit_pools_and_streak(self):
        def transport(url, headers, timeout):
            if "getTopicZTPool" in url:
                return {"data": {"pool": [{"lbc": 2}, {"lbc": "4"}, {"lbc": 1}]}}
            if "getTopicDTPool" in url:
                return {"data": {"pool": [{"c": "000001"}]}}
            if "getTopicZDFenBu" in url:
                return {"data": {"fenbu": [{"1": 200}, {"-1": 100}, {"0": 5}]}}
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            provider = EastmoneyTencentRealtimeProvider(
                transport=transport, min_interval_seconds=0,
                auction_db_path=str(Path(tmp) / "auction.sqlite3"))
            stats = provider.get_market_stats("2026-11-12")
            self.assertEqual(stats["market_limit_up_count"], 3)
            self.assertEqual(stats["market_limit_down_count"], 1)
            self.assertEqual(stats["market_max_streak"], 4)
            self.assertEqual(stats["market_advancers"], 200)
            self.assertEqual(stats["market_decliners"], 100)
            self.assertEqual(stats["market_flat"], 5)
            self.assertEqual(stats["market_breadth_ratio"], 2.0)

    def test_tencent_is_used_when_eastmoney_quote_has_no_valid_source_time(self):
        fields = [""] * 38
        fields[1], fields[2], fields[3] = "浦发银行", "600000", "10.5"
        fields[4], fields[5] = "10.24", "10.2"
        fields[30], fields[31] = "2026-11-12", "09:30:00"
        fields[32], fields[33], fields[34] = "2.54", "10.6", "10.1"
        fields[36], fields[37] = "100", "1050"

        def transport(url, headers, timeout):
            if "ulist.np/get" in url:
                return {"data": {"diff": [{
                    "f12": "600000", "f13": "1", "f2": "10.5", "f3": "2.5",
                    "f5": "100", "f6": "105000", "f17": "10.2", "f18": "10.24",
                }]}}
            if "qt.gtimg.cn" in url:
                return ('v_sh600000="' + "~".join(fields) + '";').encode("gbk")
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            provider = EastmoneyTencentRealtimeProvider(
                transport=transport, min_interval_seconds=0,
                clock=lambda: datetime(2026, 11, 12, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
                auction_db_path=str(Path(tmp) / "auction.sqlite3"))
            quote = provider.get_quotes(["sh600000"])[0]
            self.assertEqual(quote["source"], "tencent")
            self.assertEqual(quote["source_timestamp"], "2026-11-12T09:30:00+08:00")

    def test_eastmoney_batch_quote_is_primary(self):
        def transport(url, headers, timeout):
            return {"data": {"diff": [{
                "f12": "600000", "f13": "1", "f2": "10.5", "f3": "2.5",
                "f5": "100", "f6": "105000", "f10": "1.8",
                "f17": "10.2", "f18": "10.24", "f15": "10.6", "f16": "10.1",
                "f86": "2026-11-12 09:30:00",
            }]}}

        with tempfile.TemporaryDirectory() as tmp:
            provider = EastmoneyTencentRealtimeProvider(
                transport=transport, min_interval_seconds=0,
                clock=lambda: datetime(2026, 11, 12, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
                auction_db_path=str(Path(tmp) / "auction.sqlite3"))
            quote = provider.get_quotes(["sh600000"])[0]
            self.assertEqual(quote["source"], "eastmoney")
            self.assertEqual(quote["price"], 10.5)
            self.assertEqual(quote["volume_shares"], 10000)
            self.assertAlmostEqual(quote["vwap"], 10.5)
            self.assertEqual(quote["intraday_volume_ratio"], 1.8)


if __name__ == "__main__":
    unittest.main()
