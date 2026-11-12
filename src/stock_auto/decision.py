from __future__ import annotations

from .config import StrategyConfig
from .models import Decision, MarketSnapshot, Signal, TradePosition


def evaluate_entry(snapshot: MarketSnapshot, signal: Signal, config: StrategyConfig | None = None) -> Decision:
    cfg = config or StrategyConfig()
    if not signal.eligible:
        return Decision("wait", ["选股阶段未通过三驱评分或硬性过滤"], signal.warnings.copy())
    if snapshot.auction_pct is None or snapshot.auction_volume_ratio is None:
        return Decision("wait", ["竞价数据不完整，暂不生成入场信号"], ["缺少竞价涨幅或竞价量比"])
    if not cfg.auction_min_pct <= snapshot.auction_pct <= cfg.auction_max_pct:
        return Decision("wait", ["竞价涨幅超出允许区间"], [f"竞价涨幅={snapshot.auction_pct:.2f}%"])
    if snapshot.auction_volume_ratio < cfg.min_auction_volume_ratio:
        return Decision("wait", ["竞价成交量不足"], [])
    if not snapshot.quote_source_timestamp or not snapshot.order_book_source_timestamp:
        return Decision("wait", ["行情或盘口缺少上游时间戳，无法验证数据新鲜度"], ["不使用仅有本地采集时间的数据触发入场"])
    if snapshot.order_book_imbalance is None or snapshot.bid_depth_shares is None or snapshot.ask_depth_shares is None:
        return Decision("wait", ["五档盘口数据不完整，暂不生成入场信号"], ["缺少买卖盘深度或盘口失衡指标"])
    if snapshot.price is None or snapshot.vwap is None:
        return Decision("wait", ["盘中价格或分时均价线数据缺失"], ["不以缺失数据推断买点"])
    if cfg.require_price_above_vwap and snapshot.price <= snapshot.vwap:
        return Decision("wait", ["价格未运行在分时均价线上方"], [])
    if snapshot.intraday_volume_ratio is not None and snapshot.intraday_volume_ratio < 1:
        return Decision("wait", ["缺少放量确认"], ["盘中量能偏弱，等待量价重新配合"])
    reasons = ["竞价涨幅与竞价量能符合要求", "五档盘口数据完整", "盘中价格位于分时均价线上方"]
    warnings = ["盘中量比缺失，入场信号置信度降低"] if snapshot.intraday_volume_ratio is None else []
    return Decision("buy", reasons, warnings)


def evaluate_exit(snapshot: MarketSnapshot, position: TradePosition, config: StrategyConfig | None = None) -> Decision:
    cfg = config or StrategyConfig()
    if position.entry_price <= 0:
        return Decision("hold", ["持仓成本无效，无法计算收益率"], ["检查持仓数据"])
    price = snapshot.price if snapshot.price is not None else snapshot.close
    if price is None:
        return Decision("hold", ["缺少最新价格，暂不判断卖点"], ["检查行情数据"])
    pnl_pct = (price / position.entry_price - 1) * 100
    if pnl_pct <= cfg.stop_loss_pct:
        return Decision("sell", [f"触发硬止损：当前收益率{pnl_pct:.2f}%"])
    if pnl_pct >= cfg.profit_target_pct:
        return Decision("reduce", [f"达到止盈参考线：当前收益率{pnl_pct:.2f}%，考虑分批止盈"])
    high = max(position.highest_price or position.entry_price, price)
    drawdown_pct = (price / high - 1) * 100 if high > 0 else 0
    if drawdown_pct <= -cfg.trailing_drawdown_pct:
        return Decision("reduce", [f"从持仓高点回撤{abs(drawdown_pct):.2f}%，触发移动止盈参考线"])
    if snapshot.vwap is not None and price < snapshot.vwap:
        return Decision("reduce", ["价格跌破分时均价线，关注冲高回落风险"])
    return Decision("hold", [f"当前收益率{pnl_pct:.2f}%，未触发退出条件"])
