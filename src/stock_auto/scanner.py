from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .config import StrategyConfig
from .context import AuctionQuote, CapitalFlow, IntradayQuote, PointInTimeContextProvider, SectorContext
from .data import DailyBar
from .models import MarketSnapshot, RiskAssessment, Signal
from .scoring import score_snapshot


@dataclass(slots=True)
class Candidate:
    snapshot: MarketSnapshot
    signal: Signal


@dataclass(slots=True)
class ScanResult:
    trade_date: str
    candidates: list[Candidate] = field(default_factory=list)
    rejected: list[Candidate] = field(default_factory=list)

    @property
    def eligible(self) -> list[Candidate]:
        return self.candidates


class CandidateScanner:
    """Build point-in-time features from daily bars and rank the full supplied universe."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()

    def scan(
        self,
        bars: Sequence[DailyBar],
        trade_date: str,
        context_provider: PointInTimeContextProvider | None = None,
        market_context: RiskAssessment | None = None,
    ) -> ScanResult:
        by_symbol: dict[str, list[DailyBar]] = {}
        for bar in bars:
            if bar.trade_date <= trade_date:
                by_symbol.setdefault(bar.symbol, []).append(bar)
        symbols = sorted(by_symbol)
        auction: dict[str, AuctionQuote] = {}
        intraday: dict[str, IntradayQuote] = {}
        flows: dict[str, CapitalFlow] = {}
        sectors: dict[str, SectorContext] = {}
        if context_provider is not None:
            auction = {x.symbol: x for x in context_provider.get_auction_quotes(symbols, trade_date)}
            intraday = {x.symbol: x for x in context_provider.get_intraday_quotes(symbols, trade_date)}
            flows = {x.symbol: x for x in context_provider.get_capital_flows(symbols, trade_date)}
            sectors = {x.symbol: x for x in context_provider.get_sector_context(symbols, trade_date)}

        result = ScanResult(trade_date)
        for symbol in symbols:
            history = sorted(by_symbol[symbol], key=lambda x: x.trade_date)
            if not history or history[-1].trade_date != trade_date:
                continue
            snapshot = build_snapshot(history, auction.get(symbol), intraday.get(symbol),
                                      flows.get(symbol), sectors.get(symbol))
            if market_context is not None:
                # Risk level is carried by the caller; scoring remains independent of portfolio state.
                snapshot.market_limit_up_count = None
            signal = score_snapshot(snapshot, self.config)
            item = Candidate(snapshot, signal)
            (result.candidates if signal.eligible else result.rejected).append(item)
        result.candidates.sort(key=lambda x: (x.signal.score, x.signal.trend_score,
                                              x.signal.capital_score, x.signal.sentiment_score), reverse=True)
        result.rejected.sort(key=lambda x: x.signal.score, reverse=True)
        return result


def build_snapshot(
    history: Sequence[DailyBar],
    auction: AuctionQuote | None = None,
    intraday: IntradayQuote | None = None,
    flow: CapitalFlow | None = None,
    sector: SectorContext | None = None,
) -> MarketSnapshot:
    rows = sorted(history, key=lambda x: x.trade_date)
    current = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    closes = [x.close for x in rows]
    volumes = [x.volume for x in rows]
    ma = lambda n: sum(closes[-n:]) / n if len(closes) >= n else None
    avg_volume = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else None
    pct = ((current.close / current.prev_close) - 1) * 100 if current.prev_close else (
        (current.close / previous.close) - 1) * 100 if previous else None
    prior = rows[:-1]
    prior_high = max((x.high for x in prior[-20:]), default=None)
    recent_limit_up = None
    if len(prior) >= 1:
        recent_limit_up = any(
            x.prev_close is not None and x.close >= x.prev_close * (1 + x.limit_pct) * 0.999
            for x in rows[-6:-1]
        )
    amplitude = ((current.high - current.low) / current.prev_close * 100
                 if current.prev_close else None)
    return MarketSnapshot(
        symbol=current.symbol, trade_date=current.trade_date, close=current.close,
        prev_close=current.prev_close or (previous.close if previous else None),
        pct_change=pct, ma5=ma(5), ma10=ma(10), ma20=ma(20),
        volume=current.volume, avg_volume_5=avg_volume, amount=current.amount,
        amplitude=amplitude, recent_limit_up=recent_limit_up,
        prior_high=prior_high,
        auction_pct=auction.auction_pct if auction else None,
        auction_volume_ratio=auction.auction_volume_ratio if auction else None,
        price=intraday.price if intraday else None, vwap=intraday.vwap if intraday else None,
        intraday_volume_ratio=intraday.volume_ratio if intraday else None,
        main_net_inflow=flow.main_net_inflow if flow else None,
        sector_rank=sector.sector_rank if sector else None,
        sector_limit_up_count=sector.sector_limit_up_count if sector else None,
        sector_leader_limit_up=sector.sector_leader_limit_up if sector else None,
        catalyst=sector.catalyst if sector else None,
    )
