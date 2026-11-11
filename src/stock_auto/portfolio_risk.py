from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_daily_loss_pct: float = 2.0
    max_drawdown_pct: float = 10.0
    max_gross_exposure_pct: float = 80.0
    max_sector_exposure_pct: float = 35.0
    max_consecutive_losses: int = 4
    cautious_exposure_pct: float = 40.0

    def __post_init__(self) -> None:
        if min(self.max_daily_loss_pct, self.max_drawdown_pct,
               self.max_gross_exposure_pct, self.max_sector_exposure_pct,
               self.cautious_exposure_pct) < 0:
            raise ValueError("risk limits cannot be negative")
        if self.max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be positive")


@dataclass(frozen=True, slots=True)
class PortfolioRiskState:
    equity: float
    day_start_equity: float
    peak_equity: float
    gross_exposure: float
    sector_exposure: dict[str, float] = field(default_factory=dict)
    consecutive_losses: int = 0
    market_risk_level: str = "normal"


@dataclass(frozen=True, slots=True)
class PortfolioRiskDecision:
    allow_new_positions: bool
    exposure_limit_pct: float
    reasons: list[str] = field(default_factory=list)


class PortfolioRiskManager:
    """Pre-trade portfolio guardrails; amounts are currency units, limits are percentages."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def assess(self, state: PortfolioRiskState, proposed_sector: str | None = None,
               proposed_value: float = 0.0) -> PortfolioRiskDecision:
        if min(state.equity, state.day_start_equity, state.peak_equity) <= 0:
            return PortfolioRiskDecision(False, 0.0, ["账户权益基准无效，触发保护性拒绝"])
        daily_loss = max(0.0, (state.day_start_equity - state.equity) / state.day_start_equity * 100)
        drawdown = max(0.0, (state.peak_equity - state.equity) / state.peak_equity * 100)
        exposure = state.gross_exposure / state.equity * 100
        reasons: list[str] = []
        if daily_loss >= self.limits.max_daily_loss_pct:
            reasons.append(f"日内亏损达到上限：{daily_loss:.2f}%")
        if drawdown >= self.limits.max_drawdown_pct:
            reasons.append(f"账户回撤达到上限：{drawdown:.2f}%")
        if state.consecutive_losses >= self.limits.max_consecutive_losses:
            reasons.append("连续亏损次数达到熔断阈值")
        if state.market_risk_level == "risk_off":
            reasons.append("市场处于 risk_off 状态")
        if exposure >= self.limits.max_gross_exposure_pct:
            reasons.append("组合总敞口达到上限")
        if proposed_sector and proposed_value > 0:
            current = state.sector_exposure.get(proposed_sector, 0.0)
            if (current + proposed_value) / state.equity * 100 > self.limits.max_sector_exposure_pct:
                reasons.append(f"板块 {proposed_sector} 的新增仓位将超过集中度上限")
        if reasons:
            return PortfolioRiskDecision(False, 0.0, reasons)
        limit = self.limits.cautious_exposure_pct if state.market_risk_level == "cautious" else self.limits.max_gross_exposure_pct
        remaining = max(0.0, limit - exposure)
        return PortfolioRiskDecision(remaining > 0, remaining, ["组合风险约束检查通过"])
