from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Sequence

from .data import DailyBar


@dataclass(slots=True)
class DataQualityReport:
    row_count: int
    symbol_count: int
    duplicate_keys: list[str] = field(default_factory=list)
    unsorted_keys: list[str] = field(default_factory=list)
    missing_prev_close: list[str] = field(default_factory=list)
    suspicious_bars: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.row_count > 0 and not (self.duplicate_keys or self.unsorted_keys or self.suspicious_bars)


def validate_bars(bars: Sequence[DailyBar]) -> DataQualityReport:
    keys = [(bar.symbol, bar.trade_date) for bar in bars]
    counts = Counter(keys)
    duplicates = [f"{symbol} {date}" for (symbol, date), count in counts.items() if count > 1]
    sorted_keys = sorted(keys, key=lambda x: (x[1], x[0]))
    unsorted = [f"{symbol} {date}" for (symbol, date), expected in zip(keys, sorted_keys) if (symbol, date) != expected]
    missing_prev = [f"{bar.symbol} {bar.trade_date}" for bar in bars if bar.prev_close is None]
    suspicious = []
    for bar in bars:
        if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
            suspicious.append(f"{bar.symbol} {bar.trade_date}: invalid OHLC")
        if bar.volume < 0 or bar.amount is not None and bar.amount < 0:
            suspicious.append(f"{bar.symbol} {bar.trade_date}: negative volume/amount")
    return DataQualityReport(len(bars), len({bar.symbol for bar in bars}),
                              duplicates, unsorted, missing_prev, suspicious)
