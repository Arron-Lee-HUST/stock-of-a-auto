from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .data import DailyBar
from .providers import normalize_symbol


class AkshareMarketDataProvider:
    """Optional AKShare adapter for A-share daily bars and spot snapshots.

    Upstream availability and field names can change. Spot snapshots are not
    tick, order-book, or dedicated auction feeds.
    """
    def __init__(self, ak_module: Any | None = None) -> None:
        if ak_module is None:
            try:
                import akshare as ak
            except ImportError as exc:
                raise RuntimeError("install optional dependency: pip install 'stock-of-a-auto[akshare]'") from exc
            ak_module = ak
        self.ak = ak_module

    def get_bars(self, symbols: Iterable[str], start_date: str, end_date: str) -> list[DailyBar]:
        start, end = start_date.replace("-", ""), end_date.replace("-", "")
        result: list[DailyBar] = []
        for raw in sorted(set(symbols)):
            symbol = normalize_symbol(raw)
            frame = self.ak.stock_zh_a_hist(symbol=symbol[2:], period="daily",
                                            start_date=start, end_date=end, adjust="")
            rows = _records(frame)
            rows.sort(key=lambda row: str(_get(row, "日期", "")))
            previous_close = None
            for row in rows:
                raw_date = str(_get(row, "日期", "")).replace("-", "")
                if len(raw_date) != 8:
                    continue
                close = float(_get(row, "收盘"))
                result.append(DailyBar(
                    symbol=symbol, trade_date=f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}",
                    open=float(_get(row, "开盘")), high=float(_get(row, "最高")),
                    low=float(_get(row, "最低")), close=close,
                    volume=float(_get(row, "成交量")) * 100.0,
                    amount=_float_or_none(_get(row, "成交额")), prev_close=previous_close,
                    limit_pct=_default_limit_pct(symbol)))
                previous_close = close
        return sorted(result, key=lambda bar: (bar.trade_date, bar.symbol))

    def get_spot_quotes(self, symbols: Iterable[str] | None = None) -> list[dict[str, Any]]:
        """Return normalized latest spot quotes, with a local capture timestamp."""
        wanted = {normalize_symbol(item) for item in symbols} if symbols is not None else None
        frame = self.ak.stock_zh_a_spot_em()
        captured_at = datetime.now().astimezone().isoformat()
        output = []
        for row in _records(frame):
            code = str(_get(row, "代码", "")).strip()
            if not code:
                continue
            symbol = _symbol_from_code(code)
            if wanted is not None and symbol not in wanted:
                continue
            output.append({
                "symbol": symbol, "name": str(_get(row, "名称", "")),
                "price": _float_or_none(_get(row, "最新价")),
                "pct_change": _float_or_none(_get(row, "涨跌幅")),
                "volume_shares": (_float_or_none(_get(row, "成交量")) or 0.0) * 100.0,
                "amount_cny": _float_or_none(_get(row, "成交额")),
                "captured_at": captured_at, "source": "akshare.stock_zh_a_spot_em"})
        return output


def _records(frame: Any) -> list[Any]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        try:
            return frame.to_dict("records")
        except TypeError:
            pass
    return list(frame)


def _get(row: Any, key: str, default: Any = None) -> Any:
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _symbol_from_code(code: str) -> str:
    if code.startswith(("6", "9")):
        return "sh" + code
    if code.startswith(("4", "8")):
        return "bj" + code
    return "sz" + code


def _default_limit_pct(symbol: str) -> float:
    code = symbol[2:]
    if symbol.startswith("bj"):
        return 0.30
    if code.startswith(("300", "301", "688", "689")):
        return 0.20
    return 0.10
