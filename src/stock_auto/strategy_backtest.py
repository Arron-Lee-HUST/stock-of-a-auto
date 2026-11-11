from __future__ import annotations

from collections.abc import Callable, Sequence

from .backtest import BacktestConfig, BacktestEngine, BacktestResult, BacktestPosition
from .context import PointInTimeContextProvider
from .data import DailyBar
from .models import MarketSnapshot, TradePosition
from .decision import evaluate_exit
from .scanner import CandidateScanner


ContextFactory = Callable[[str], PointInTimeContextProvider | None]


class ThreeDriveBacktest:
    """End-to-end daily strategy backtest with point-in-time enrichment per session."""

    def __init__(self, config=None, backtest_config: BacktestConfig | None = None) -> None:
        self.scanner = CandidateScanner(config)
        self.engine = BacktestEngine(backtest_config)

    def run(self, bars: Sequence[DailyBar],
            context_factory: ContextFactory | None = None) -> BacktestResult:
        def select_entries(date, history):
            visible = [bar for rows in history.values() for bar in rows if bar.trade_date <= date]
            provider = context_factory(date) if context_factory else None
            result = self.scanner.scan(visible, date, provider)
            return [item.snapshot.symbol for item in result.candidates]

        def select_exits(date, position: BacktestPosition, history):
            rows = history
            if not rows:
                return False
            last = rows[-1]
            if last.trade_date != date:
                return False
            highest = max((bar.high for bar in rows if bar.trade_date >= position.entry_date),
                          default=position.entry_price)
            snapshot = MarketSnapshot(
                symbol=position.symbol, trade_date=date, close=last.close,
                price=last.close, vwap=None,
            )
            model_position = TradePosition(
                symbol=position.symbol, entry_price=position.entry_price,
                quantity=position.quantity, entry_date=position.entry_date,
                highest_price=max(position.entry_price, highest),
                cost_basis=position.entry_cost,
            )
            position.entry_price = model_position.entry_price
            position.quantity = model_position.quantity
            return evaluate_exit(snapshot, model_position, self.scanner.config).action in {"sell", "reduce"}

        return self.engine.run(bars, select_entries, select_exits)
