from __future__ import annotations

import os
from typing import Any, Iterable

from .data import DailyBar, MarketDataProvider


def normalize_symbol(symbol: str) -> str:
    """Convert 600000.SH / sh600000 / 000001.SZ to lowercase sh/sz notation."""
    value = symbol.strip().upper()
    if value.startswith(("SH", "SZ", "BJ")) and len(value) == 8:
        return value.lower()
    if "." in value:
        code, exchange = value.split(".", 1)
        prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(exchange)
        if prefix:
            return prefix + code
    raise ValueError(f"unsupported A-share symbol: {symbol}")


def to_tushare_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    return f"{normalized[2:]}.{normalized[:2].upper()}"


class TushareMarketDataProvider(MarketDataProvider):
    """Optional Tushare Pro daily-bar adapter. Pass an existing pro client for tests/use.

    Install the optional SDK with: pip install 'stock-of-a-auto[tushare]'
    Set TUSHARE_TOKEN in the environment; never commit API tokens.
    """
    def __init__(self, pro_client: Any | None = None, token: str | None = None) -> None:
        if pro_client is None:
            token = token or os.getenv("TUSHARE_TOKEN")
            if not token:
                raise ValueError("TUSHARE_TOKEN is required for Tushare data access")
            try:
                import tushare as ts
            except ImportError as exc:
                raise RuntimeError("install the optional dependency: pip install 'stock-of-a-auto[tushare]'") from exc
            ts.set_token(token)
            pro_client = ts.pro_api()
        self.pro = pro_client

    def get_bars(self, symbols: Iterable[str], start_date: str, end_date: str) -> list[DailyBar]:
        result: list[DailyBar] = []
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        for symbol in sorted(set(symbols)):
            frame = self.pro.daily(ts_code=to_tushare_symbol(symbol), start_date=start, end_date=end)
            for row in _records(frame):
                trade_date = str(_value(row, "trade_date")).replace("-", "")
                trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                result.append(DailyBar(
                    symbol=normalize_symbol(str(_value(row, "ts_code", to_tushare_symbol(symbol)))),
                    trade_date=trade_date,
                    open=float(_value(row, "open")), high=float(_value(row, "high")),
                    low=float(_value(row, "low")), close=float(_value(row, "close")),
                    volume=float(_value(row, "vol")) * 100.0,
                    amount=float(_value(row, "amount")) * 1000.0 if _value(row, "amount") is not None else None,
                    prev_close=float(_value(row, "pre_close")) if _value(row, "pre_close") is not None else None,
                    limit_pct=0.10,
                ))
        return sorted(result, key=lambda bar: (bar.trade_date, bar.symbol))


def _records(frame: Any) -> list[Any]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        try:
            return frame.to_dict("records")
        except TypeError:
            pass
    return list(frame)


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)
