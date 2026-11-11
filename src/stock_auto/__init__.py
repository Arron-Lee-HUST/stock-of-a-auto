"""A-share short-term strategy research engine."""

from .backtest import BacktestConfig, BacktestEngine, BacktestResult, Trade
from .data import CsvMarketDataProvider, DailyBar, MarketDataProvider
from .providers import TushareMarketDataProvider
from .context import AuctionQuote, CapitalFlow, CsvPointInTimeContextProvider, IntradayQuote, PointInTimeContextProvider, SectorContext
from .scanner import Candidate, CandidateScanner, ScanResult, build_snapshot
from .strategy_backtest import ThreeDriveBacktest
from .monitor import MarketMonitor, MonitorEvent, MonitorReport
from .service import JsonlAlertSink, MonitorService, TradingCalendar
from .portfolio_risk import (PortfolioRiskDecision, PortfolioRiskManager, PortfolioRiskState, RiskLimits)
from .paper import PaperBroker, PaperAccount, PaperFill, PaperOrder, PaperPosition
from .validation import DataQualityReport, validate_bars
from .reporting import write_backtest_reports, write_dashboard, write_json, write_scan_reports
from .config import StrategyConfig
from .decision import evaluate_entry, evaluate_exit
from .models import MarketSnapshot, Signal, TradePosition
from .pipeline import evaluate_candidate
from .risk import assess_market_risk, calculate_position_size
from .scoring import score_snapshot

__all__ = [
    "BacktestConfig", "BacktestEngine", "BacktestResult", "CsvMarketDataProvider",
    "DailyBar", "MarketDataProvider", "TushareMarketDataProvider",
    "AuctionQuote", "CapitalFlow", "CsvPointInTimeContextProvider", "IntradayQuote", "PointInTimeContextProvider", "SectorContext",
    "Candidate", "CandidateScanner", "ScanResult", "ThreeDriveBacktest", "build_snapshot",
    "MarketMonitor", "MonitorEvent", "MonitorReport", "MonitorService", "TradingCalendar", "JsonlAlertSink", "PortfolioRiskDecision",
    "PortfolioRiskManager", "PortfolioRiskState", "RiskLimits",
    "PaperBroker", "PaperAccount", "PaperFill", "PaperOrder", "PaperPosition",
    "DataQualityReport", "validate_bars", "write_backtest_reports", "write_dashboard", "write_json", "write_scan_reports", "MarketSnapshot", "Signal", "StrategyConfig", "Trade", "TradePosition",
    "assess_market_risk", "calculate_position_size", "evaluate_candidate",
    "evaluate_entry", "evaluate_exit", "score_snapshot",
]
