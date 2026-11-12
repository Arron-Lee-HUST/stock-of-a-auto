from __future__ import annotations

import sqlite3
from pathlib import Path


class AuctionHistoryStore:
    """Persist final opening-auction matched volumes and calculate 竞昨量比.

    The ratio is today's matched auction volume / the most recent earlier
    trading day's stored matched volume. It is None until a baseline exists.
    """
    def __init__(self, path: str | Path = "runtime/auction-history.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS auction_volume (
                symbol TEXT NOT NULL, trade_date TEXT NOT NULL,
                volume_shares REAL NOT NULL, PRIMARY KEY(symbol, trade_date))""")

    def record(self, symbol: str, trade_date: str, volume_shares: float) -> float | None:
        if volume_shares <= 0:
            return None
        with sqlite3.connect(self.path, timeout=10) as db:
            previous = db.execute(
                "SELECT volume_shares FROM auction_volume WHERE symbol=? AND trade_date<? ORDER BY trade_date DESC LIMIT 1",
                (symbol, trade_date),
            ).fetchone()
            db.execute(
                "INSERT INTO auction_volume(symbol, trade_date, volume_shares) VALUES (?, ?, ?) "
                "ON CONFLICT(symbol, trade_date) DO UPDATE SET volume_shares=excluded.volume_shares",
                (symbol, trade_date, volume_shares),
            )
        if not previous or previous[0] <= 0:
            return None
        return volume_shares / float(previous[0])
