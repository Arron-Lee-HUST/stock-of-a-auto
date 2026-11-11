from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Iterable


@dataclass(frozen=True, slots=True)
class AuctionQuote:
    symbol: str
    trade_date: str
    auction_pct: float | None = None
    auction_volume_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class IntradayQuote:
    symbol: str
    trade_date: str
    price: float | None = None
    vwap: float | None = None
    volume_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class CapitalFlow:
    symbol: str
    trade_date: str
    main_net_inflow: float | None = None


@dataclass(frozen=True, slots=True)
class SectorContext:
    symbol: str
    trade_date: str
    sector_rank: int | None = None
    sector_limit_up_count: int | None = None
    sector_leader_limit_up: bool | None = None
    catalyst: bool | None = None


class PointInTimeContextProvider(Protocol):
    """Optional enrichment provider; values must be observable no later than trade_date."""
    def get_auction_quotes(self, symbols: Iterable[str], trade_date: str) -> list[AuctionQuote]: ...
    def get_intraday_quotes(self, symbols: Iterable[str], trade_date: str) -> list[IntradayQuote]: ...
    def get_capital_flows(self, symbols: Iterable[str], trade_date: str) -> list[CapitalFlow]: ...
    def get_sector_context(self, symbols: Iterable[str], trade_date: str) -> list[SectorContext]: ...


class CsvPointInTimeContextProvider:
    """Read four normalized point-in-time CSV files; omitted files yield empty context.

    Columns are documented in docs/data-providers.md. Each lookup is restricted to
    the requested trade_date to prevent accidental use of later observations.
    """
    def __init__(self, auction_path=None, intraday_path=None, flow_path=None, sector_path=None):
        from pathlib import Path
        self.paths = {
            "auction": Path(auction_path) if auction_path else None,
            "intraday": Path(intraday_path) if intraday_path else None,
            "flow": Path(flow_path) if flow_path else None,
            "sector": Path(sector_path) if sector_path else None,
        }

    def _rows(self, key, symbols, trade_date):
        import csv
        path = self.paths[key]
        if path is None or not path.exists():
            return []
        wanted = set(symbols)
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [row for row in csv.DictReader(stream)
                    if row.get("symbol") in wanted and row.get("trade_date") == trade_date]

    def get_auction_quotes(self, symbols, trade_date):
        return [AuctionQuote(r["symbol"], trade_date, _number(r.get("auction_pct")),
                             _number(r.get("auction_volume_ratio")))
                for r in self._rows("auction", symbols, trade_date)]

    def get_intraday_quotes(self, symbols, trade_date):
        return [IntradayQuote(r["symbol"], trade_date, _number(r.get("price")),
                              _number(r.get("vwap")), _number(r.get("volume_ratio")))
                for r in self._rows("intraday", symbols, trade_date)]

    def get_capital_flows(self, symbols, trade_date):
        return [CapitalFlow(r["symbol"], trade_date, _number(r.get("main_net_inflow")))
                for r in self._rows("flow", symbols, trade_date)]

    def get_sector_context(self, symbols, trade_date):
        return [SectorContext(r["symbol"], trade_date, _integer(r.get("sector_rank")),
                              _integer(r.get("sector_limit_up_count")),
                              _boolean(r.get("sector_leader_limit_up")), _boolean(r.get("catalyst")))
                for r in self._rows("sector", symbols, trade_date)]


def _number(value):
    return float(value) if value not in (None, "") else None


def _integer(value):
    return int(value) if value not in (None, "") else None


def _boolean(value):
    if value in (None, ""):
        return None
    return value.strip().lower() in {"1", "true", "yes"}
