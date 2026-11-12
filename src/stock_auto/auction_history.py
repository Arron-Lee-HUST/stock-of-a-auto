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
            db.execute("""CREATE TABLE IF NOT EXISTS auction_observations (
                symbol TEXT NOT NULL, trade_date TEXT NOT NULL,
                source_timestamp TEXT NOT NULL, logical_auction_time TEXT NOT NULL,
                indicative_price REAL, auction_price REAL,
                matched_volume_shares REAL, matched_amount_cny REAL,
                source TEXT NOT NULL,
                PRIMARY KEY(symbol, trade_date, source_timestamp))""")

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

    def record_observation(self, observation: dict) -> None:
        """Persist a point-in-time auction sample without treating indicative volume as matched volume."""
        required = ("symbol", "trade_date", "source_timestamp", "logical_auction_time", "source")
        if any(not observation.get(key) for key in required):
            return
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute(
                """INSERT INTO auction_observations(
                    symbol, trade_date, source_timestamp, logical_auction_time,
                    indicative_price, auction_price, matched_volume_shares,
                    matched_amount_cny, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date, source_timestamp) DO UPDATE SET
                    logical_auction_time=excluded.logical_auction_time,
                    indicative_price=excluded.indicative_price,
                    auction_price=excluded.auction_price,
                    matched_volume_shares=excluded.matched_volume_shares,
                    matched_amount_cny=excluded.matched_amount_cny,
                    source=excluded.source""",
                (observation["symbol"], observation["trade_date"],
                 observation["source_timestamp"], observation["logical_auction_time"],
                 observation.get("indicative_price"), observation.get("auction_price"),
                 observation.get("auction_volume_shares"), observation.get("auction_amount_cny"),
                 observation["source"]),
            )

    def observations(self, symbol: str, trade_date: str) -> list[dict]:
        """Return chronological observed auction samples for audit/backtest use."""
        with sqlite3.connect(self.path, timeout=10) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """SELECT symbol, trade_date, source_timestamp, logical_auction_time,
                          indicative_price, auction_price, matched_volume_shares,
                          matched_amount_cny, source
                   FROM auction_observations
                   WHERE symbol=? AND trade_date=? ORDER BY source_timestamp""",
                (symbol, trade_date),
            ).fetchall()
        return [dict(row) for row in rows]
