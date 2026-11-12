from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(slots=True)
class MarketSnapshot:
    """Normalized point-in-time market data; percentage fields use percentage points.

    Example: pct_change=3.2 means +3.2%, not 0.032.
    Missing data must be None, never a fabricated zero.
    """

    symbol: str
    name: str = ""
    trade_date: str = ""
    close: float | None = None
    prev_close: float | None = None
    pct_change: float | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    volume: float | None = None
    avg_volume_5: float | None = None
    amount: float | None = None
    main_net_inflow: float | None = None
    fund_flow_small_net: float | None = None
    fund_flow_mid_net: float | None = None
    fund_flow_big_net: float | None = None
    fund_flow_super_big_net: float | None = None
    fund_flow_source: str | None = None
    fund_flow_kind: str | None = None
    fund_flow_source_timestamp: str | None = None
    amplitude: float | None = None
    recent_limit_up: bool | None = None
    prior_high: float | None = None
    platform_high: float | None = None
    sector_rank: int | None = None
    sector_limit_up_count: int | None = None
    sector_leader_limit_up: bool | None = None
    catalyst: bool | None = None
    auction_pct: float | None = None
    auction_indicative_pct: float | None = None
    auction_indicative_price: float | None = None
    auction_indicative_source_timestamp: str | None = None
    auction_volume_ratio: float | None = None
    price: float | None = None
    vwap: float | None = None
    intraday_volume_ratio: float | None = None
    intraday_high: float | None = None
    intraday_low: float | None = None
    auction_matched_volume: float | None = None
    auction_amount: float | None = None
    best_bid_price: float | None = None
    best_ask_price: float | None = None
    bid_depth_shares: float | None = None
    ask_depth_shares: float | None = None
    order_book_imbalance: float | None = None
    order_book_complete: bool | None = None
    bid_levels: int | None = None
    ask_levels: int | None = None
    quote_source: str | None = None
    order_book_source: str | None = None
    auction_source: str | None = None
    quote_captured_at: str | None = None
    quote_source_timestamp: str | None = None
    order_book_captured_at: str | None = None
    order_book_source_timestamp: str | None = None
    auction_source_timestamp: str | None = None
    market_limit_up_count: int | None = None
    market_limit_down_count: int | None = None
    market_max_streak: int | None = None
    market_advancers: int | None = None
    market_decliners: int | None = None
    market_flat: int | None = None
    market_breadth_ratio: float | None = None


@dataclass(slots=True)
class Signal:
    symbol: str
    score: float
    trend_score: float
    capital_score: float
    sentiment_score: float
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TradePosition:
    symbol: str
    entry_price: float
    quantity: int
    entry_date: str = ""
    highest_price: float | None = None
    cost_basis: float | None = None


@dataclass(slots=True)
class RiskAssessment:
    level: Literal["normal", "cautious", "risk_off"]
    exposure_limit: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Decision:
    action: Literal["buy", "hold", "sell", "reduce", "wait"]
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
