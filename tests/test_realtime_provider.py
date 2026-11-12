import tempfile
import unittest
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

    def test_eastmoney_batch_quote_is_primary(self):
        def transport(url, headers, timeout):
            return {"data": {"diff": [{
                "f12": "600000", "f13": "1", "f2": "10.5", "f3": "2.5",
                "f5": "100", "f6": "105000", "f10": "1.8",
                "f17": "10.2", "f18": "10.24", "f15": "10.6", "f16": "10.1",
            }]}}

        with tempfile.TemporaryDirectory() as tmp:
            provider = EastmoneyTencentRealtimeProvider(
                transport=transport, min_interval_seconds=0,
                auction_db_path=str(Path(tmp) / "auction.sqlite3"))
            quote = provider.get_quotes(["sh600000"])[0]
            self.assertEqual(quote["source"], "eastmoney")
            self.assertEqual(quote["price"], 10.5)
            self.assertEqual(quote["volume_shares"], 10000)
            self.assertAlmostEqual(quote["vwap"], 10.5)
            self.assertEqual(quote["intraday_volume_ratio"], 1.8)


if __name__ == "__main__":
    unittest.main()
