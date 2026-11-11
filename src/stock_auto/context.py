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
