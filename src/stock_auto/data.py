from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Iterable


@dataclass(frozen=True, slots=True)
class DailyBar:
    """One normalized A-share daily OHLCV bar; prices are unadjusted currency units."""
    symbol: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float | None = None
    prev_close: float | None = None
    is_suspended: bool = False
    limit_pct: float = 0.10

    def __post_init__(self) -> None:
        if not self.symbol or not self.trade_date:
            raise ValueError("symbol and trade_date are required")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be the maximum OHLC price")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be the minimum OHLC price")
        if self.volume < 0 or not 0 < self.limit_pct < 1:
            raise ValueError("volume must be non-negative and limit_pct in (0, 1)")


class MarketDataProvider(Protocol):
    def get_bars(self, symbols: Iterable[str], start_date: str, end_date: str) -> list[DailyBar]:
        """Return bars sorted by (trade_date, symbol), with no future rows outside the range."""
        ...


class CsvMarketDataProvider:
    """Read normalized CSV data; provider-specific downloads stay outside the core package.

    Required columns: symbol,trade_date,open,high,low,close,volume.
    Optional: amount,prev_close,is_suspended,limit_pct.
    """
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def get_bars(self, symbols: Iterable[str], start_date: str, end_date: str) -> list[DailyBar]:
        wanted = set(symbols)
        result: list[DailyBar] = []
        with self.path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row["symbol"] not in wanted or not start_date <= row["trade_date"] <= end_date:
                    continue
                result.append(DailyBar(
                    symbol=row["symbol"], trade_date=row["trade_date"],
                    open=float(row["open"]), high=float(row["high"]),
                    low=float(row["low"]), close=float(row["close"]),
                    volume=float(row["volume"]),
                    amount=_optional_float(row.get("amount")),
                    prev_close=_optional_float(row.get("prev_close")),
                    is_suspended=(row.get("is_suspended", "").strip().lower() in {"1", "true", "yes"}),
                    limit_pct=float(row.get("limit_pct") or 0.10),
                ))
        return sorted(result, key=lambda bar: (bar.trade_date, bar.symbol))


def _optional_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None
