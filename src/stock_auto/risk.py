from __future__ import annotations

from .config import StrategyConfig
from .models import MarketSnapshot, RiskAssessment


def assess_market_risk(snapshot: MarketSnapshot, config: StrategyConfig | None = None) -> RiskAssessment:
    cfg = config or StrategyConfig()
    if snapshot.market_limit_up_count is None or snapshot.market_limit_down_count is None or snapshot.market_max_streak is None:
        return RiskAssessment("cautious", cfg.cautious_exposure_pct, ["市场情绪统计数据不完整，采用谨慎仓位"])
    if (
        snapshot.market_limit_up_count < cfg.market_limit_up_floor
        or snapshot.market_limit_down_count > cfg.market_limit_down_ceiling
        or snapshot.market_max_streak < cfg.max_streak_floor
    ):
        return RiskAssessment("risk_off", cfg.risk_off_exposure_pct, ["市场赚钱效应减弱或亏钱效应上升"])
    return RiskAssessment("normal", 1.0, ["市场情绪指标未触发风险退潮条件"])


def calculate_position_size(
    total_equity: float, available_cash: float, price: float, open_positions: int,
    risk: RiskAssessment, config: StrategyConfig | None = None,
) -> int:
    """Return board-lot (100-share) quantity under exposure and slot limits."""
    cfg = config or StrategyConfig()
    if min(total_equity, available_cash, price) <= 0:
        return 0
    slots_left = cfg.max_positions - open_positions
    if slots_left <= 0:
        return 0
    allocation = min(
        total_equity * cfg.max_single_position_pct,
        total_equity * risk.exposure_limit / slots_left,
        available_cash,
    )
    return (int(allocation // price) // 100) * 100
