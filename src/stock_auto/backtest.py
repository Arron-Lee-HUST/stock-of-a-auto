from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from .data import DailyBar


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.0005
    slippage_rate: float = 0.001
    min_commission: float = 5.0
    board_lot: int = 100
    max_positions: int = 5
    max_single_position_pct: float = 0.20
    allow_limit_up_buy: bool = False
    allow_limit_down_sell: bool = False

    def __post_init__(self) -> None:
        if self.initial_cash <= 0 or self.board_lot <= 0 or self.max_positions < 1:
            raise ValueError("invalid capital, board_lot or max_positions")
        if not 0 < self.max_single_position_pct <= 1:
            raise ValueError("max_single_position_pct must be in (0, 1]")
        if min(self.commission_rate, self.stamp_duty_rate, self.slippage_rate, self.min_commission) < 0:
            raise ValueError("fees and slippage cannot be negative")


@dataclass(slots=True)
class BacktestPosition:
    symbol: str
    quantity: int
    entry_date: str
    entry_price: float
    entry_cost: float


@dataclass(frozen=True, slots=True)
class Trade:
    symbol: str
    entry_date: str
    exit_date: str
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    return_pct: float


@dataclass(slots=True)
class BacktestResult:
    initial_cash: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[str, float]] = field(default_factory=list)
    rejected_orders: list[str] = field(default_factory=list)


# The callback only receives bars dated on or before decision_date. Orders are
# executed at the following trading session's open, preventing same-bar look-ahead.
EntrySelector = Callable[[str, Mapping[str, Sequence[DailyBar]]], Sequence[str]]
ExitSelector = Callable[[str, BacktestPosition, Sequence[DailyBar]], bool]


class BacktestEngine:
    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(
        self,
        bars: Sequence[DailyBar],
        entry_selector: EntrySelector,
        exit_selector: ExitSelector,
    ) -> BacktestResult:
        cfg = self.config
        by_date: dict[str, dict[str, DailyBar]] = {}
        history: dict[str, list[DailyBar]] = {}
        for bar in sorted(bars, key=lambda item: (item.trade_date, item.symbol)):
            by_date.setdefault(bar.trade_date, {})[bar.symbol] = bar
            history.setdefault(bar.symbol, []).append(bar)
        dates = sorted(by_date)
        if len(dates) < 2:
            raise ValueError("at least two trading dates are required")

        cash = cfg.initial_cash
        positions: dict[str, BacktestPosition] = {}
        trades: list[Trade] = []
        rejected: list[str] = []
        equity_curve: list[tuple[str, float]] = []

        for index, date in enumerate(dates[:-1]):
            today = by_date[date]
            next_date = dates[index + 1]
            tomorrow = by_date[next_date]
            visible = {symbol: tuple(b for b in rows if b.trade_date <= date) for symbol, rows in history.items()}

            # Decisions at close; execute exits at next session open. T+1 is enforced
            # because a position opened at next_date cannot be exited until a later date.
            for symbol, position in list(positions.items()):
                rows = visible.get(symbol, ())
                if rows and exit_selector(date, position, rows):
                    bar = tomorrow.get(symbol)
                    if bar is None or bar.is_suspended or not cfg.allow_limit_down_sell and _at_limit(bar, bar.open, -1, today.get(symbol).close if today.get(symbol) else None):
                        rejected.append(f"{next_date} {symbol}: exit blocked (missing/suspended/limit-down)")
                        continue
                    exit_price = bar.open * (1 - cfg.slippage_rate)
                    gross = exit_price * position.quantity
                    fee = max(gross * cfg.commission_rate, cfg.min_commission) + gross * cfg.stamp_duty_rate
                    proceeds = gross - fee
                    cash += proceeds
                    pnl = proceeds - position.entry_cost
                    trades.append(Trade(symbol, position.entry_date, next_date, position.quantity,
                                        position.entry_price, exit_price, pnl, pnl / position.entry_cost * 100))
                    del positions[symbol]

            selected = list(dict.fromkeys(entry_selector(date, visible)))
            for symbol in selected:
                if symbol in positions or len(positions) >= cfg.max_positions:
                    continue
                bar = tomorrow.get(symbol)
                if bar is None or bar.is_suspended:
                    rejected.append(f"{next_date} {symbol}: entry blocked (missing/suspended)")
                    continue
                if not cfg.allow_limit_up_buy and _at_limit(bar, bar.open, 1, today.get(symbol).close if today.get(symbol) else None):
                    rejected.append(f"{next_date} {symbol}: entry blocked (limit-up)")
                    continue
                price = bar.open * (1 + cfg.slippage_rate)
                allocation = min(cash, cfg.initial_cash * cfg.max_single_position_pct)
                quantity = int(allocation / price) // cfg.board_lot * cfg.board_lot
                while quantity > 0:
                    gross = price * quantity
                    fee = max(gross * cfg.commission_rate, cfg.min_commission)
                    if gross + fee <= cash:
                        break
                    quantity -= cfg.board_lot
                if quantity <= 0:
                    rejected.append(f"{next_date} {symbol}: insufficient cash for one board lot")
                    continue
                gross = price * quantity
                fee = max(gross * cfg.commission_rate, cfg.min_commission)
                cash -= gross + fee
                positions[symbol] = BacktestPosition(symbol, quantity, next_date, price, gross + fee)

            equity = cash + sum(
                (tomorrow.get(symbol).close if tomorrow.get(symbol) else position.entry_price) * position.quantity
                for symbol, position in positions.items()
            )
            equity_curve.append((next_date, equity))

        # Mark remaining positions to the last available close; no forced liquidation.
        last_date = dates[-1]
        last = by_date[last_date]
        final_equity = cash + sum(last.get(s, None).close * p.quantity if last.get(s) else p.entry_price * p.quantity
                                  for s, p in positions.items())
        if not equity_curve or equity_curve[-1][0] != last_date:
            equity_curve.append((last_date, final_equity))
        peak = cfg.initial_cash
        max_dd = 0.0
        for _, equity in equity_curve:
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak * 100)
        wins = sum(t.pnl > 0 for t in trades)
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = -sum(t.pnl for t in trades if t.pnl < 0)
        return BacktestResult(
            cfg.initial_cash, final_equity, (final_equity / cfg.initial_cash - 1) * 100,
            max_dd, wins / len(trades) * 100 if trades else 0.0,
            gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0),
            trades, equity_curve, rejected,
        )


def _at_limit(bar: DailyBar, price: float, direction: int, fallback_prev_close: float | None = None) -> bool:
    previous_close = bar.prev_close if bar.prev_close is not None else fallback_prev_close
    if previous_close is None:
        return False
    limit_price = previous_close * (1 + direction * bar.limit_pct)
    return price >= limit_price * 0.9995 if direction > 0 else price <= limit_price * 1.0005
