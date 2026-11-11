from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Mapping

from .config import StrategyConfig
from .decision import evaluate_entry, evaluate_exit
from .models import Decision, MarketSnapshot, Signal, TradePosition
from .risk import assess_market_risk


@dataclass(slots=True)
class MonitorEvent:
    symbol: str
    phase: str
    action: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MonitorReport:
    trade_date: str
    checked_at: str
    market_risk: str
    events: list[MonitorEvent] = field(default_factory=list)


class MarketMonitor:
    """Pure monitoring logic; caller owns scheduling, market data polling and alert delivery."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()

    def evaluate(
        self,
        trade_date: str,
        checked_at: str,
        snapshots: Mapping[str, MarketSnapshot],
        signals: Mapping[str, Signal],
        positions: Mapping[str, TradePosition],
        market_snapshot: MarketSnapshot,
    ) -> MonitorReport:
        now = time.fromisoformat(checked_at)
        risk = assess_market_risk(market_snapshot, self.config)
        report = MonitorReport(trade_date, checked_at, risk.level)
        auction_phase = time(9, 20) <= now <= time(9, 25)
        intraday_phase = now >= time(9, 30) and now <= time(15, 0)

        if not (auction_phase or intraday_phase):
            report.events.append(MonitorEvent("*", "outside_session", "no_action",
                                               ["当前不在竞价监控或连续交易时段"]))
            return report

        for symbol, snapshot in snapshots.items():
            if snapshot.trade_date and snapshot.trade_date != trade_date:
                report.events.append(MonitorEvent(symbol, "data_check", "skip",
                                                   ["行情交易日期与监控日期不一致"]))
                continue
            if symbol in positions:
                decision = evaluate_exit(snapshot, positions[symbol], self.config)
                if decision.action in {"sell", "reduce"}:
                    report.events.append(_event(symbol, "position", decision))
                continue
            signal = signals.get(symbol)
            if signal is None or not signal.eligible:
                continue
            if auction_phase:
                if snapshot.auction_pct is None or snapshot.auction_volume_ratio is None:
                    report.events.append(MonitorEvent(symbol, "auction", "wait",
                                                       ["竞价涨幅或竞价量比缺失"]))
                elif not self.config.auction_min_pct <= snapshot.auction_pct <= self.config.auction_max_pct:
                    report.events.append(MonitorEvent(symbol, "auction", "reject",
                                                       ["竞价涨幅超出策略允许区间"]))
                elif snapshot.auction_volume_ratio < self.config.min_auction_volume_ratio:
                    report.events.append(MonitorEvent(symbol, "auction", "wait",
                                                       ["竞价量比不足"]))
                else:
                    report.events.append(MonitorEvent(symbol, "auction", "watch",
                                                       ["竞价条件通过，等待开盘后量价确认"]))
            elif intraday_phase:
                decision = evaluate_entry(snapshot, signal, self.config)
                if decision.action != "wait" or decision.warnings:
                    report.events.append(_event(symbol, "intraday", decision))
        return report


def _event(symbol: str, phase: str, decision: Decision) -> MonitorEvent:
    return MonitorEvent(symbol, phase, decision.action, decision.reasons, decision.warnings)
