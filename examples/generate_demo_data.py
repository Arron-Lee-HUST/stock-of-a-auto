from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path


def trading_dates(count=30):
    result, current = [], date(2024, 1, 2)
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    root = Path("examples/data")
    dates = trading_dates()
    symbols = ["sh600000", "sz000001", "sh600036"]
    universe = [[symbol] for symbol in symbols]
    daily, auction, intraday, flow, sector = [], [], [], [], []
    for index, symbol in enumerate(symbols):
        close = 10.0 + index * 5
        for day_index, day in enumerate(dates):
            previous = close
            close = previous * 1.04
            volume = int(10000 * (1.10 ** day_index))
            daily.append([symbol, day, round(previous * 1.01, 4), round(close * 1.045, 4),
                          round(previous * 0.995, 4), round(close, 4), volume,
                          round(volume * close, 2), round(previous, 4), 0, 0.10])
            auction.append([symbol, day, 2.5, 2.0])
            intraday.append([symbol, day, round(close * 1.005, 4), round(close * 0.995, 4), 1.5])
            flow.append([symbol, day, 1000000])
            sector.append([symbol, day, index + 1, 3, "true", "true"])
    write_csv(root / "universe.csv", ["symbol"], universe)
    write_csv(root / "daily.csv", ["symbol", "trade_date", "open", "high", "low", "close",
             "volume", "amount", "prev_close", "is_suspended", "limit_pct"], daily)
    write_csv(root / "auction.csv", ["symbol", "trade_date", "auction_pct", "auction_volume_ratio"], auction)
    write_csv(root / "intraday.csv", ["symbol", "trade_date", "price", "vwap", "volume_ratio"], intraday)
    write_csv(root / "flow.csv", ["symbol", "trade_date", "main_net_inflow"], flow)
    write_csv(root / "sector.csv", ["symbol", "trade_date", "sector_rank", "sector_limit_up_count",
             "sector_leader_limit_up", "catalyst"], sector)
    write_csv(root / "paper-orders.csv", ["order_id", "symbol", "side", "quantity", "submitted_date", "trade_date"],\n              [["demo-buy-001", symbols[0], "BUY", 100, dates[-2], dates[-1]]])\n    print(f"Synthetic demo data written to {root}; not real market data.")


if __name__ == "__main__":
    main()
