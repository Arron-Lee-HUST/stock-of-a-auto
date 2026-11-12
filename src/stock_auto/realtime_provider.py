from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .providers import normalize_symbol
from .auction_history import AuctionHistoryStore

LOG = logging.getLogger(__name__)
UT = "fa5fd1943c7b386f172d6893dbbd1d0c"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
QUOTE_FIELDS = ",".join([
    "f43", "f44", "f45", "f46", "f47", "f48", "f50", "f57", "f58",
    "f60", "f86", "f169", "f170", "f168",
    "f19", "f20", "f17", "f18", "f15", "f16", "f13", "f14", "f11", "f12",
    "f39", "f40", "f37", "f38", "f35", "f36", "f33", "f34", "f31", "f32",
])


def _number(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _secid(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    code = normalized[2:]
    market = "1" if normalized.startswith("sh") else "0"
    return f"{market}.{code}"


def _valid_price(value: float | None) -> bool:
    return value is not None and value > 0


class EastmoneyTencentRealtimeProvider:
    """Eastmoney-first public A-share quote adapter, Tencent fallback, Sina last resort.

    Public web endpoints are undocumented/uncontracted and may rate-limit or change.
    Auction data and order-book depth are Eastmoney-only; a fallback spot quote must
    never be represented as an auction or order-book observation.
    """

    def __init__(
        self,
        transport: Callable[[str, dict[str, str], float], Any] | None = None,
        timeout_seconds: float = 6.0,
        min_interval_seconds: float = 0.18,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        auction_db_path: str = "runtime/auction-history.sqlite3",
    ) -> None:
        self.transport = transport or self._http_json
        self.timeout_seconds = timeout_seconds
        self.min_interval_seconds = min_interval_seconds
        self.clock = clock or (lambda: datetime.now().astimezone())
        self.sleeper = sleeper
        self._last_request = 0.0
        self.auction_history = AuctionHistoryStore(auction_db_path)

    @staticmethod
    def _http_json(url: str, headers: dict[str, str], timeout: float) -> Any:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
        # Eastmoney JSON is UTF-8; Tencent/Sina quote endpoints return text.
        decoded = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(decoded)
        except json.JSONDecodeError:
            return raw

    def _get(self, base: str, params: dict[str, str], headers: dict[str, str] | None = None) -> Any:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval_seconds:
            self.sleeper(self.min_interval_seconds - elapsed)
        self._last_request = time.monotonic()
        return self.transport(base + "?" + urlencode(params), headers or HEADERS, self.timeout_seconds)

    def get_quotes(self, symbols: Iterable[str]) -> list[dict[str, Any]]:
        normalized = sorted({normalize_symbol(s) for s in symbols})
        if not normalized:
            return []
        output: dict[str, dict[str, Any]] = {}
        secids = ",".join(_secid(s) for s in normalized)
        try:
            payload = self._get(
                "https://push2.eastmoney.com/api/qt/ulist.np/get",
                {"fltt": "2", "invt": "2", "fields": "f2,f3,f4,f5,f6,f10,f12,f13,f14,f15,f16,f17,f18",
                 "secids": secids, "ut": UT},
            )
            rows = (payload.get("data") or {}).get("diff") or []
            for row in rows:
                symbol = self._symbol(str(row.get("f12", "")), str(row.get("f13", "")))
                quote = self._normalize_quote(
                    symbol, row.get("f2"), row.get("f3"), row.get("f17"), row.get("f18"),
                    row.get("f15"), row.get("f16"), row.get("f5"), row.get("f6"),
                    "eastmoney", self.clock().isoformat(),
                )
                if quote:
                    quote["intraday_volume_ratio"] = _number(row.get("f10"))
                    quote["vwap"] = (quote["amount_cny"] / quote["volume_shares"]
                                     if quote.get("amount_cny") and quote.get("volume_shares") else None)
                    output[symbol] = quote
        except Exception:
            LOG.exception("Eastmoney batch quote failed; falling back to Tencent/Sina")

        missing = [s for s in normalized if s not in output]
        for symbol in missing:
            quote = self._get_tencent_quote(symbol)
            if quote is None:
                quote = self._get_sina_quote(symbol)
            if quote is not None:
                output[symbol] = quote
        return [output[s] for s in normalized if s in output]

    def get_order_books(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for raw in sorted(set(symbols)):
            symbol = normalize_symbol(raw)
            try:
                payload = self._get(
                    "https://push2.eastmoney.com/api/qt/stock/get",
                    {"secid": _secid(symbol), "fltt": "2", "invt": "2",
                     "fields": QUOTE_FIELDS, "ut": UT},
                )
                data = payload.get("data") or {}
                bids, asks = [], []
                for price_key, volume_key in (("f19", "f20"), ("f17", "f18"), ("f15", "f16"),
                                               ("f13", "f14"), ("f11", "f12")):
                    price, volume = _number(data.get(price_key)), _number(data.get(volume_key))
                    if _valid_price(price) and volume is not None:
                        bids.append({"price": price, "volume_shares": volume * 100})
                for price_key, volume_key in (("f39", "f40"), ("f37", "f38"), ("f35", "f36"),
                                               ("f33", "f34"), ("f31", "f32")):
                    price, volume = _number(data.get(price_key)), _number(data.get(volume_key))
                    if _valid_price(price) and volume is not None:
                        asks.append({"price": price, "volume_shares": volume * 100})
                if bids or asks:
                    bid_total = sum(x["volume_shares"] for x in bids)
                    ask_total = sum(x["volume_shares"] for x in asks)
                    result[symbol] = {
                        "symbol": symbol, "bids": bids, "asks": asks,
                        "bid_depth_shares": bid_total, "ask_depth_shares": ask_total,
                        "best_bid_price": bids[0]["price"] if bids else None,
                        "best_ask_price": asks[0]["price"] if asks else None,
                        "book_imbalance": ((bid_total - ask_total) / (bid_total + ask_total))
                            if bid_total + ask_total else None,
                        "captured_at": self.clock().isoformat(), "source": "eastmoney.stock.get",
                        "levels": 5,
                    }
            except Exception:
                LOG.exception("Eastmoney order book failed for %s", symbol)
        return result

    def get_auction_observations(self, symbols: Iterable[str], trade_date: str) -> dict[str, dict[str, Any]]:
        """Read the final 09:25 auction match from the Eastmoney 09:26 trend row.

        Eastmoney's source label is 09:26 for the final 09:25 match. Earlier virtual
        indicative rows have zero matched volume and are intentionally ignored.
        """
        result: dict[str, dict[str, Any]] = {}
        for raw in sorted(set(symbols)):
            symbol = normalize_symbol(raw)
            try:
                payload = self._get(
                    "https://push2.eastmoney.com/api/qt/stock/trends2/get",
                    {"secid": _secid(symbol), "ndays": "1", "iscr": "0",
                     "fields1": "f1,f2,f3,f4,f5,f6", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
                     "ut": UT},
                )
                rows = ((payload.get("data") or {}).get("trends") or [])
                for raw_row in rows:
                    parts = str(raw_row).split(",")
                    if len(parts) < 7:
                        continue
                    stamp = parts[0].strip()
                    if not stamp.startswith(trade_date):
                        continue
                    clock = stamp[-5:]
                    volume_hands = _number(parts[5])
                    price = _number(parts[2])
                    amount = _number(parts[6])
                    if clock == "09:26" and volume_hands is not None and volume_hands > 0 and _valid_price(price):
                        volume_shares = volume_hands * 100
                        result[symbol] = {
                            "symbol": symbol, "trade_date": trade_date,
                            "logical_auction_time": "09:25", "source_timestamp": stamp,
                            "auction_price": price, "auction_volume_shares": volume_shares,
                            "auction_amount_cny": amount,
                            "auction_volume_ratio": self.auction_history.record(symbol, trade_date, volume_shares),
                            "source": "eastmoney.trends2",
                        }
                        break
            except Exception:
                LOG.exception("Eastmoney auction observation failed for %s", symbol)
        return result

    def _get_tencent_quote(self, symbol: str) -> dict[str, Any] | None:
        try:
            payload = self._get("https://qt.gtimg.cn", {"q": symbol}, {"Referer": "https://gu.qq.com/",
                "User-Agent": HEADERS["User-Agent"]})
            if isinstance(payload, dict):
                return None
            text = str(payload)
            if isinstance(payload, bytes):
                text = payload.decode("gbk", errors="replace")
            fields = text.split('="', 1)[-1].strip().strip('";').split("~")
            if len(fields) < 34:
                return None
            return self._normalize_quote(symbol, fields[3], fields[32], fields[5], fields[4],
                                         fields[33], fields[34] if len(fields) > 34 else None,
                                         fields[36] if len(fields) > 36 else None,
                                         fields[37] if len(fields) > 37 else None,
                                         "tencent", self.clock().isoformat(), volume_unit="hands",
                                         amount_unit="10k")
        except Exception:
            LOG.exception("Tencent fallback quote failed for %s", symbol)
            return None

    def _get_sina_quote(self, symbol: str) -> dict[str, Any] | None:
        try:
            payload = self.transport("https://hq.sinajs.cn/list=" + symbol,
                {"Referer": "https://finance.sina.com.cn/", "User-Agent": HEADERS["User-Agent"]},
                self.timeout_seconds)
            if isinstance(payload, dict):
                return None
            raw = payload.decode("gbk", errors="replace") if isinstance(payload, bytes) else str(payload)
            fields = raw.split('="', 1)[-1].strip().strip('";').split(",")
            if len(fields) < 10:
                return None
            return self._normalize_quote(symbol, fields[3], None, fields[1], fields[2],
                                         fields[4], fields[5], fields[8], fields[9],
                                         "sina", self.clock().isoformat(), volume_unit="hands")
        except Exception:
            LOG.exception("Sina fallback quote failed for %s", symbol)
            return None

    @staticmethod
    def _symbol(code: str, market: str) -> str:
        if not code:
            return ""
        if market == "1" or code.startswith(("6", "9", "5")):
            return "sh" + code
        if code.startswith(("4", "8")):
            return "bj" + code
        return "sz" + code

    @staticmethod
    def _normalize_quote(symbol: str, price: Any, pct: Any, open_price: Any,
                         prev_close: Any, high: Any, low: Any, volume: Any, amount: Any,
                         source: str, captured_at: str, volume_unit: str = "hands",
                         amount_unit: str = "cny") -> dict[str, Any] | None:
        price_n = _number(price)
        if not _valid_price(price_n):
            return None
        volume_n, amount_n = _number(volume), _number(amount)
        if volume_n is not None and volume_unit == "hands":
            volume_n *= 100
        if amount_n is not None and amount_unit == "10k":
            amount_n *= 10000
        return {
            "symbol": symbol, "price": price_n, "pct_change": _number(pct),
            "open": _number(open_price), "prev_close": _number(prev_close),
            "high": _number(high), "low": _number(low),
            "volume_shares": volume_n, "amount_cny": amount_n,
            "captured_at": captured_at, "source": source,
            "vwap": (amount_n / volume_n if amount_n and volume_n else None),
            "intraday_volume_ratio": None,
            "auction_available": False, "order_book_available": False,
        }
