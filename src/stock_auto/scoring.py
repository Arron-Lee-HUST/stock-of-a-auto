from __future__ import annotations

from .config import StrategyConfig
from .models import MarketSnapshot, Signal


def score_snapshot(snapshot: MarketSnapshot, config: StrategyConfig | None = None) -> Signal:
    """Score the three drives. Scores are explainable and bounded to 100."""
    cfg = config or StrategyConfig()
    missing: list[str] = []
    reasons: list[str] = []
    warnings: list[str] = []

    trend = 0.0
    if snapshot.close is None:
        missing.append("close")
    else:
        for field, ma, weight in (
            ("ma5", snapshot.ma5, 10.0),
            ("ma10", snapshot.ma10, 8.0),
            ("ma20", snapshot.ma20, 7.0),
        ):
            if ma is None:
                missing.append(field)
            elif snapshot.close > ma:
                trend += weight
                reasons.append(f"收盘价站上{field.upper()}")
        if snapshot.pct_change is None:
            missing.append("pct_change")
        elif cfg.min_pct_change <= snapshot.pct_change <= cfg.max_pct_change:
            trend += 5.0
            reasons.append("当日涨幅处于强势观察区间")
        if snapshot.recent_limit_up is True:
            trend += 5.0
            reasons.append("近期出现涨停，股性活跃")
        elif snapshot.amplitude is not None and snapshot.amplitude >= cfg.min_amplitude:
            trend += 3.0
            reasons.append("近期振幅达到活跃阈值")
        elif snapshot.recent_limit_up is None and snapshot.amplitude is None:
            missing.extend(["recent_limit_up", "amplitude"])
        if snapshot.prior_high is not None and snapshot.close > snapshot.prior_high:
            trend += 5.0
            reasons.append("收盘价突破前期高点")
        elif snapshot.platform_high is not None and snapshot.close > snapshot.platform_high:
            trend += 5.0
            reasons.append("收盘价突破整理平台")
        elif snapshot.prior_high is None and snapshot.platform_high is None:
            missing.append("prior_high/platform_high")

    capital = 0.0
    if snapshot.volume is None or snapshot.avg_volume_5 is None:
        missing.extend([f for f, v in (("volume", snapshot.volume), ("avg_volume_5", snapshot.avg_volume_5)) if v is None])
    elif snapshot.avg_volume_5 > 0:
        ratio = snapshot.volume / snapshot.avg_volume_5
        if ratio >= cfg.min_volume_ratio:
            capital += 15.0
            reasons.append(f"成交量放大至近5日均量的{ratio:.2f}倍")
        elif ratio >= 1.0:
            capital += 7.0
            warnings.append("成交量仅略高于近期均量")
    if snapshot.pct_change is not None and snapshot.volume is not None and snapshot.prev_close is not None:
        if snapshot.pct_change > 0 and snapshot.close is not None and snapshot.close > snapshot.prev_close:
            capital += 5.0
            reasons.append("上涨伴随成交量，量价方向一致")
    if snapshot.main_net_inflow is None:
        missing.append("main_net_inflow")
    elif snapshot.main_net_inflow > cfg.strong_main_flow_ratio:
        capital += 10.0
        reasons.append("主力资金净流入为正")
    elif cfg.prefer_positive_main_flow:
        warnings.append("主力资金未呈现净流入")

    sentiment = 0.0
    if snapshot.sector_rank is None:
        missing.append("sector_rank")
    elif snapshot.sector_rank <= cfg.hot_sector_top_n:
        sentiment += 10.0
        reasons.append("所属板块处于市场热门排名")
    if snapshot.sector_limit_up_count is None:
        missing.append("sector_limit_up_count")
    elif snapshot.sector_limit_up_count >= cfg.min_sector_limit_ups:
        sentiment += 8.0
        reasons.append("所属板块存在涨停梯队")
    if snapshot.sector_leader_limit_up is None:
        missing.append("sector_leader_limit_up")
    elif snapshot.sector_leader_limit_up:
        sentiment += 7.0
        reasons.append("板块龙头封板，题材强度得到确认")
    if snapshot.catalyst is None:
        missing.append("catalyst")
    elif snapshot.catalyst:
        sentiment += 5.0
        reasons.append("存在消息或事件催化")

    trend_score = min(40.0, trend)
    capital_score = min(30.0, capital)
    sentiment_score = min(30.0, sentiment)
    total = trend_score + capital_score + sentiment_score

    hard_failures: list[str] = []
    if snapshot.pct_change is None or not cfg.min_pct_change <= snapshot.pct_change <= cfg.max_pct_change:
        hard_failures.append("涨幅不在配置区间或数据缺失")
    if snapshot.close is None:
        hard_failures.append("缺少收盘价")
    else:
        for enabled, ma, label in (
            (cfg.require_above_ma5, snapshot.ma5, "MA5"),
            (cfg.require_above_ma10, snapshot.ma10, "MA10"),
            (cfg.require_above_ma20, snapshot.ma20, "MA20"),
        ):
            if enabled and (ma is None or snapshot.close <= ma):
                hard_failures.append(f"未满足站上{label}条件")
    if snapshot.volume is None or snapshot.avg_volume_5 is None or snapshot.avg_volume_5 <= 0:
        hard_failures.append("成交量数据不完整")
    elif snapshot.volume / snapshot.avg_volume_5 < cfg.min_volume_ratio:
        hard_failures.append("成交量未达到放量阈值")
    if total < cfg.min_total_score:
        hard_failures.append(f"综合评分低于阈值{cfg.min_total_score:g}")
    if trend_score < cfg.min_trend_score:
        hard_failures.append("趋势动能评分不足")
    if capital_score < cfg.min_capital_score:
        hard_failures.append("资金博弈评分不足")
    if sentiment_score < cfg.min_sentiment_score:
        hard_failures.append("市场情绪评分不足")

    warnings.extend(hard_failures)
    return Signal(
        symbol=snapshot.symbol,
        score=round(total, 2),
        trend_score=round(trend_score, 2),
        capital_score=round(capital_score, 2),
        sentiment_score=round(sentiment_score, 2),
        eligible=not hard_failures,
        reasons=reasons,
        warnings=warnings,
        missing_fields=sorted(set(missing)),
    )
