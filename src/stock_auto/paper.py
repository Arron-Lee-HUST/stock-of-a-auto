from __future__ import annotations

from dataclasses import dataclass, field

from .backtest import BacktestConfig
from .data import DailyBar


@dataclass(slots=True)
class PaperOrder:
    order_id: str
    symbol: str
    side: str
    quantity: int
    submitted_date: str
    status: str = "pending"
    reason: str = ""


@dataclass(slots=True)
class PaperPosition:
    symbol: str
    quantity: int
    entry_date: str
    average_price: float
    cost_basis: float


@dataclass(frozen=True, slots=True)
class PaperFill:
    order_id: str
    symbol: str
    side: str
    trade_date: str
    quantity: int
    price: float
    fee: float


@dataclass(slots=True)
class PaperAccount:
    initial_cash: float
    cash: float
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    orders: dict[str, PaperOrder] = field(default_factory=dict)
    fills: list[PaperFill] = field(default_factory=list)


class PaperBroker:
    """Deterministic local simulator; no network, broker credentials or live order route."""

    def __init__(self, initial_cash: float = 1_000_000.0,
                 config: BacktestConfig | None = None) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.config = config or BacktestConfig(initial_cash=initial_cash)
        self.account = PaperAccount(initial_cash, initial_cash)

    def submit_order(self, order_id: str, symbol: str, side: str, quantity: int,
                     submitted_date: str) -> PaperOrder:
        if order_id in self.account.orders:
            return self.account.orders[order_id]
        order = PaperOrder(order_id, symbol, side.upper(), quantity, submitted_date)
        if order.side not in {"BUY", "SELL"}:
            order.status, order.reason = "rejected", "side must be BUY or SELL"
        elif quantity <= 0 or quantity % self.config.board_lot:
            order.status, order.reason = "rejected", "quantity must be a positive board-lot multiple"
        self.account.orders[order_id] = order
        return order

    def process_bar(self, bar: DailyBar) -> list[PaperFill]:
        fills: list[PaperFill] = []
        for order in self.account.orders.values():
            if order.status != "pending" or order.symbol != bar.symbol or bar.trade_date <= order.submitted_date:
                continue
            if bar.is_suspended:
                order.status, order.reason = "rejected", "suspended"
                continue
            cfg = self.config
            previous_close = bar.prev_close
            if previous_close is None:
                order.status, order.reason = "rejected", "missing_prev_close; cannot verify A-share price limits"
                continue
            if previous_close is not None:
                limit_up = previous_close * (1 + bar.limit_pct)
                limit_down = previous_close * (1 - bar.limit_pct)
                if order.side == "BUY" and not cfg.allow_limit_up_buy and bar.open >= limit_up * 0.9995:
                    order.status, order.reason = "rejected", "limit_up"
                    continue
                if order.side == "SELL" and not cfg.allow_limit_down_sell and bar.open <= limit_down * 1.0005:
                    order.status, order.reason = "rejected", "limit_down"
                    continue
            price = bar.open * (1 + cfg.slippage_rate if order.side == "BUY" else 1 - cfg.slippage_rate)
            gross = price * order.quantity
            commission = max(gross * cfg.commission_rate, cfg.min_commission)
            stamp = gross * cfg.stamp_duty_rate if order.side == "SELL" else 0.0
            fee = commission + stamp
            if order.side == "BUY":
                if order.symbol in self.account.positions:
                    order.status, order.reason = "rejected", "position already exists; averaging is disabled"
                    continue
                if gross + fee > self.account.cash:
                    order.status, order.reason = "rejected", "insufficient cash"
                    continue
                self.account.cash -= gross + fee
                self.account.positions[order.symbol] = PaperPosition(
                    order.symbol, order.quantity, bar.trade_date, price, gross + fee
                )
            else:
                position = self.account.positions.get(order.symbol)
                if position is None or position.quantity < order.quantity:
                    order.status, order.reason = "rejected", "insufficient position"
                    continue
                if position.entry_date >= bar.trade_date:
                    continue
                self.account.cash += gross - fee
                remaining = position.quantity - order.quantity
                if remaining:
                    position.quantity = remaining
                    position.cost_basis *= remaining / (remaining + order.quantity)
                else:
                    del self.account.positions[order.symbol]
            order.status = "filled"
            fill = PaperFill(order.order_id, order.symbol, order.side, bar.trade_date,
                             order.quantity, price, fee)
            self.account.fills.append(fill)
            fills.append(fill)
        return fills

    def equity(self, latest_prices: dict[str, float] | None = None) -> float:
        prices = latest_prices or {}
        return self.account.cash + sum(
            prices.get(symbol, position.average_price) * position.quantity
            for symbol, position in self.account.positions.items()
        )
