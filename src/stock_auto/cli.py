from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .backtest import BacktestConfig
from .context import CsvPointInTimeContextProvider
from .data import CsvMarketDataProvider
from .paper import PaperBroker
from .monitor import MarketMonitor
from .models import MarketSnapshot, TradePosition
from .scanner import build_snapshot
from .reporting import write_backtest_reports, write_dashboard, write_json, write_scan_reports
from .scanner import CandidateScanner
from .strategy_backtest import ThreeDriveBacktest
from .validation import validate_bars


def _symbols(path: str) -> list[str]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        if not rows.fieldnames or "symbol" not in rows.fieldnames:
            raise ValueError("universe CSV must contain a symbol column")
        return sorted({row["symbol"].strip() for row in rows if row.get("symbol", "").strip()})


def _context(args, date):
    if not any((args.auction_csv, args.intraday_csv, args.flow_csv, args.sector_csv)):
        return None
    return CsvPointInTimeContextProvider(args.auction_csv, args.intraday_csv,
                                         args.flow_csv, args.sector_csv)


def _add_context_args(parser):
    parser.add_argument("--auction-csv")
    parser.add_argument("--intraday-csv")
    parser.add_argument("--flow-csv")
    parser.add_argument("--sector-csv")


def _add_market_args(parser):
    parser.add_argument("--daily-csv", required=True)
    parser.add_argument("--universe-csv", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output-dir", default="reports")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="stock-auto", description="A-share three-drive research and paper trading toolkit")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="scan the universe and export candidates")
    _add_market_args(scan)
    _add_context_args(scan)
    scan.add_argument("--trade-date", required=True)

    backtest = commands.add_parser("backtest", help="run the three-drive historical backtest")
    _add_market_args(backtest)
    _add_context_args(backtest)

    validate = commands.add_parser("validate-data", help="validate normalized daily bars")
    validate.add_argument("--daily-csv", required=True)
    validate.add_argument("--universe-csv", required=True)
    validate.add_argument("--start-date", required=True)
    validate.add_argument("--end-date", required=True)
    validate.add_argument("--output", default="reports/data-quality.json")

    monitor = commands.add_parser("monitor", help="evaluate auction or intraday signals from CSV snapshots")
    _add_market_args(monitor)
    _add_context_args(monitor)
    monitor.add_argument("--signal-date", required=True)
    monitor.add_argument("--trade-date", required=True)
    monitor.add_argument("--checked-at", required=True)
    monitor.add_argument("--market-stats-json", required=True)
    monitor.add_argument("--positions-csv")
    monitor.add_argument("--output", default="reports/monitor.json")

    sync_ak = commands.add_parser("sync-akshare", help="download AKShare daily bars into normalized CSV")
    sync_ak.add_argument("--universe-csv", required=True)
    sync_ak.add_argument("--start-date", required=True)
    sync_ak.add_argument("--end-date", required=True)
    sync_ak.add_argument("--output", default="data/akshare-daily.csv")

    spot_ak = commands.add_parser("spot-akshare", help="export an AKShare latest spot snapshot")
    spot_ak.add_argument("--universe-csv")
    spot_ak.add_argument("--output", default="runtime/akshare-spot.csv")

    serve_ak = commands.add_parser("serve-akshare", help="run read-only AKShare polling with fail-closed entry signals")
    serve_ak.add_argument("--daily-csv", required=True, help="cached normalized daily bars")
    serve_ak.add_argument("--universe-csv", required=True)
    serve_ak.add_argument("--start-date", required=True)
    serve_ak.add_argument("--calendar-csv", required=True, help="authoritative trade_date CSV")
    serve_ak.add_argument("--positions-csv")
    serve_ak.add_argument("--poll-interval", type=float, default=30.0)
    serve_ak.add_argument("--alerts-db", default="runtime/alerts.sqlite3")
    serve_ak.add_argument("--health", default="runtime/health.json")
    serve_ak.add_argument("--log-file", default="runtime/service.log")
    serve_ak.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    paper = commands.add_parser("paper-replay", help="replay pre-approved paper orders against daily bars")
    paper.add_argument("--daily-csv", required=True)
    paper.add_argument("--orders-csv", required=True)
    paper.add_argument("--initial-cash", type=float, default=1_000_000)
    paper.add_argument("--output", default="reports/paper-account.json")

    args = parser.parse_args(argv)
    if args.command == "sync-akshare":
        from .akshare_provider import AkshareMarketDataProvider
        provider = AkshareMarketDataProvider()
        bars = provider.get_bars(_symbols(args.universe_csv), args.start_date, args.end_date)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["symbol", "trade_date", "open", "high", "low", "close",
                             "volume", "amount", "prev_close", "is_suspended", "limit_pct"])
            for bar in bars:
                writer.writerow([bar.symbol, bar.trade_date, bar.open, bar.high, bar.low,
                                 bar.close, bar.volume, bar.amount, bar.prev_close,
                                 bar.is_suspended, bar.limit_pct])
        print(f"AKShare daily sync complete: {len(bars)} rows -> {output}")
        return 0

    if args.command == "spot-akshare":
        from .akshare_provider import AkshareMarketDataProvider
        symbols = _symbols(args.universe_csv) if args.universe_csv else None
        quotes = AkshareMarketDataProvider().get_spot_quotes(symbols)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fields = ["symbol", "name", "price", "pct_change", "volume_shares",
                  "amount_cny", "captured_at", "source"]
        with output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(quotes)
        print(f"AKShare spot snapshot complete: {len(quotes)} rows -> {output}")
        return 0

    if args.command == "serve-akshare":
        import logging
        import os
        import signal
        from logging.handlers import RotatingFileHandler
        from .akshare_provider import AkshareMarketDataProvider
        from .service import MonitorService, TradingCalendar, SqliteAlertSink
        from .monitor import MarketMonitor
        from .models import MarketSnapshot, TradePosition
        from .scanner import CandidateScanner, build_snapshot

        symbols = _symbols(args.universe_csv)
        calendar = TradingCalendar.from_csv(args.calendar_csv)
        daily = CsvMarketDataProvider(args.daily_csv)
        live = AkshareMarketDataProvider()
        monitor = MarketMonitor()

        def monitor_cycle(trade_date, checked_at):
            history_bars = daily.get_bars(symbols, args.start_date, trade_date)
            completed_dates = sorted({bar.trade_date for bar in history_bars if bar.trade_date < trade_date})
            if not completed_dates:
                raise RuntimeError("no completed daily bars before current trade date")
            signal_date = completed_dates[-1]
            scan = CandidateScanner().scan(history_bars, signal_date)
            signals = {item.signal.symbol: item.signal for item in scan.candidates}
            by_symbol = {}
            for bar in history_bars:
                if bar.trade_date <= signal_date:
                    by_symbol.setdefault(bar.symbol, []).append(bar)

            positions = {}
            if args.positions_csv:
                with Path(args.positions_csv).open("r", encoding="utf-8-sig", newline="") as stream:
                    for row in csv.DictReader(stream):
                        positions[row["symbol"]] = TradePosition(
                            row["symbol"], float(row["entry_price"]), int(row["quantity"]),
                            row.get("entry_date", ""),
                            float(row["highest_price"]) if row.get("highest_price") else None,
                            float(row["cost_basis"]) if row.get("cost_basis") else None)

            quotes = {item["symbol"]: item for item in live.get_spot_quotes(set(signals) | set(positions))}
            snapshots = {}
            for symbol in sorted(set(signals) | set(positions)):
                if symbol not in by_symbol:
                    continue
                snapshot = build_snapshot(by_symbol[symbol])
                quote = quotes.get(symbol)
                snapshot.trade_date = trade_date
                if quote and quote.get("price") is not None:
                    snapshot.price = quote["price"]
                    snapshot.close = quote["price"]
                    snapshot.pct_change = quote.get("pct_change")
                else:
                    # Never fall back to yesterday's close for a live exit decision.
                    snapshot.price = None
                    snapshot.close = None
                snapshots[symbol] = snapshot

            # Missing market breadth forces cautious exposure. Missing auction/VWAP
            # fields deliberately prevent any buy action from this spot-only adapter.
            market = MarketSnapshot(symbol="market", trade_date=trade_date)
            return monitor.evaluate(trade_date, checked_at, snapshots, signals, positions, market)

        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(level=getattr(logging, args.log_level),
                            handlers=[RotatingFileHandler(log_path, maxBytes=10_000_000,
                                                          backupCount=5, encoding="utf-8"),
                                      logging.StreamHandler()],
                            format="%(asctime)s %(levelname)s %(name)s %(message)s")
        service = MonitorService(calendar, monitor_cycle, SqliteAlertSink(args.alerts_db,
                                 webhook_url=os.getenv("STOCK_AUTO_ALERT_WEBHOOK")),
                                 args.health, interval_seconds=args.poll_interval,
                                 max_backoff_seconds=max(60.0, args.poll_interval))
        signal.signal(signal.SIGINT, lambda *_: service.stop())
        signal.signal(signal.SIGTERM, lambda *_: service.stop())
        print("Starting read-only AKShare monitor. Auction/VWAP are unavailable; new entries remain blocked.")
        service.run_forever()
        return 0

    if args.command == "validate-data":
        bars = CsvMarketDataProvider(args.daily_csv).get_bars(
            _symbols(args.universe_csv), args.start_date, args.end_date)
        report = validate_bars(bars)
        write_json(args.output, report)
        print(json.dumps({"valid": report.valid, "rows": report.row_count,
                          "symbols": report.symbol_count, "output": args.output}, ensure_ascii=False))
        return 0 if report.valid else 2

    if args.command == "monitor":
        universe = _symbols(args.universe_csv)
        positions = {}
        if args.positions_csv:
            with Path(args.positions_csv).open("r", encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    positions[row["symbol"]] = TradePosition(
                        row["symbol"], float(row["entry_price"]), int(row["quantity"]),
                        row.get("entry_date", ""),
                        float(row["highest_price"]) if row.get("highest_price") else None,
                        float(row["cost_basis"]) if row.get("cost_basis") else None)
        symbols = sorted(set(universe) | set(positions))
        bars = CsvMarketDataProvider(args.daily_csv).get_bars(symbols, args.start_date, args.signal_date)
        signal_context = _context(args, args.signal_date)
        scan_result = CandidateScanner().scan(bars, args.signal_date, signal_context)
        signal_map = {item.signal.symbol: item.signal for item in scan_result.candidates}
        grouped = {}
        for bar in bars:
            grouped.setdefault(bar.symbol, []).append(bar)
        live_context = _context(args, args.trade_date)
        auction = {x.symbol: x for x in live_context.get_auction_quotes(symbols, args.trade_date)} if live_context else {}
        intraday = {x.symbol: x for x in live_context.get_intraday_quotes(symbols, args.trade_date)} if live_context else {}
        snapshots = {}
        for symbol in sorted(set(signal_map) | set(positions)):
            if symbol not in grouped:
                continue
            snap = build_snapshot(grouped[symbol], auction.get(symbol), intraday.get(symbol))
            snap.trade_date = args.trade_date
            snapshots[symbol] = snap
        market_stats = json.loads(Path(args.market_stats_json).read_text(encoding="utf-8"))
        market_snapshot = MarketSnapshot(symbol="market", trade_date=args.trade_date, **market_stats)
        report = MarketMonitor().evaluate(args.trade_date, args.checked_at, snapshots,
                                          signal_map, positions, market_snapshot)
        write_json(args.output, report)
        print(f"monitor complete: {len(report.events)} events, market_risk={report.market_risk}")
        return 0

    if args.command == "paper-replay":
        with Path(args.orders_csv).open("r", encoding="utf-8-sig", newline="") as stream:
            orders = list(csv.DictReader(stream))
        symbols = sorted({row["symbol"] for row in orders})
        bars = CsvMarketDataProvider(args.daily_csv).get_bars(
            symbols, min(row["submitted_date"] for row in orders),
            max(row["trade_date"] for row in orders))
        broker = PaperBroker(args.initial_cash)
        for row in orders:
            broker.submit_order(row["order_id"], row["symbol"], row["side"],
                                int(row["quantity"]), row["submitted_date"])
        for bar in bars:
            broker.process_bar(bar)
        payload = {
            "cash": broker.account.cash,
            "positions": {s: vars(p) if hasattr(p, "__dict__") else {
                "symbol": p.symbol, "quantity": p.quantity, "entry_date": p.entry_date,
                "average_price": p.average_price, "cost_basis": p.cost_basis
            } for s, p in broker.account.positions.items()},
            "orders": [{"order_id": o.order_id, "symbol": o.symbol, "side": o.side,
                        "quantity": o.quantity, "status": o.status, "reason": o.reason}
                       for o in broker.account.orders.values()],
            "fills": [{"order_id": f.order_id, "symbol": f.symbol, "side": f.side,
                       "trade_date": f.trade_date, "quantity": f.quantity,
                       "price": f.price, "fee": f.fee} for f in broker.account.fills],
        }
        write_json(args.output, payload)
        print(f"paper replay complete: {args.output}")
        return 0

    symbols = _symbols(args.universe_csv)
    bars = CsvMarketDataProvider(args.daily_csv).get_bars(symbols, args.start_date, args.end_date)
    if args.command == "scan":
        provider = _context(args, args.trade_date)
        result = CandidateScanner().scan(bars, args.trade_date, provider)
        write_scan_reports(result, args.output_dir)
        rows = [{"symbol": x.signal.symbol, "score": x.signal.score,
                 "trend": x.signal.trend_score, "capital": x.signal.capital_score,
                 "sentiment": x.signal.sentiment_score} for x in result.candidates]
        write_dashboard(Path(args.output_dir) / "index.html", "三驱候选扫描",
                        {"交易日": args.trade_date, "合格候选": len(result.candidates),
                         "未通过": len(result.rejected)}, rows)
        print(f"scan complete: {len(result.candidates)} eligible, {len(result.rejected)} rejected")
        return 0
    factory = lambda date: _context(args, date)
    result = ThreeDriveBacktest(backtest_config=BacktestConfig()).run(bars, factory)
    write_backtest_reports(result, args.output_dir)
    write_dashboard(Path(args.output_dir) / "index.html", "三驱策略回测",
                    {"初始资金": result.initial_cash, "期末权益": round(result.final_equity, 2),
                     "收益率": f"{result.total_return_pct:.2f}%",
                     "最大回撤": f"{result.max_drawdown_pct:.2f}%",
                     "胜率": f"{result.win_rate_pct:.2f}%", "交易次数": len(result.trades)},
                    [{"symbol": t.symbol, "entry": t.entry_date, "exit": t.exit_date,
                      "pnl": round(t.pnl, 2), "return": f"{t.return_pct:.2f}%"} for t in result.trades],
                    result.equity_curve)
    print(f"backtest complete: return={result.total_return_pct:.2f}% trades={len(result.trades)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
