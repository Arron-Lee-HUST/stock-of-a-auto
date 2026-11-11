from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    # Trend drive
    min_pct_change: float = 2.0
    max_pct_change: float = 8.0
    require_above_ma5: bool = True
    require_above_ma10: bool = True
    require_above_ma20: bool = True
    min_volume_ratio: float = 1.5
    min_amplitude: float = 3.0
    require_recent_activity: bool = False

    # Capital drive
    prefer_positive_main_flow: bool = True
    strong_main_flow_ratio: float = 0.0
    breakout_lookback_high: bool = True

    # Sentiment drive
    hot_sector_top_n: int = 10
    min_sector_limit_ups: int = 1
    require_sector_leader: bool = False

    # Score thresholds
    min_total_score: float = 60.0
    min_trend_score: float = 18.0
    min_capital_score: float = 12.0
    min_sentiment_score: float = 8.0

    # Dynamic entry / exit
    auction_min_pct: float = 0.0
    auction_max_pct: float = 5.0
    min_auction_volume_ratio: float = 1.0
    require_price_above_vwap: bool = True
    profit_target_pct: float = 6.0
    stop_loss_pct: float = -4.0
    trailing_drawdown_pct: float = 3.0

    # Portfolio / market risk
    max_positions: int = 5
    max_single_position_pct: float = 0.20
    cautious_exposure_pct: float = 0.50
    risk_off_exposure_pct: float = 0.0
    market_limit_up_floor: int = 20
    market_limit_down_ceiling: int = 20
    max_streak_floor: int = 2

    def __post_init__(self) -> None:
        if self.min_pct_change > self.max_pct_change:
            raise ValueError("min_pct_change cannot exceed max_pct_change")
        if not 0 <= self.max_single_position_pct <= 1:
            raise ValueError("max_single_position_pct must be between 0 and 1")
        if not 0 <= self.cautious_exposure_pct <= 1:
            raise ValueError("cautious_exposure_pct must be between 0 and 1")
        if self.max_positions < 1:
            raise ValueError("max_positions must be at least 1")
