"""A-share short-term strategy research engine."""

from .backtest import BacktestConfig, BacktestEngine, BacktestResult, Trade
from .data import CsvMarketDataProvider, DailyBar, MarketDataProvider
from .config import StrategyConfig
from .decision import evaluate_entry, evaluate_exit
from .models import MarketSnapshot, Signal, TradePosition
from .pipeline import evaluate_candidate
from .risk import assess_market_risk, calculate_position_size
from .scoring import score_snapshot

__all__ = [
    "BacktestConfig", "BacktestEngine", "BacktestResult", "CsvMarketDataProvider",
    "DailyBar", "MarketDataProvider", "MarketSnapshot", "Signal", "StrategyConfig", "Trade", "TradePosition",
    "assess_market_risk", "calculate_position_size", "evaluate_candidate",
    "evaluate_entry", "evaluate_exit", "score_snapshot",
]
