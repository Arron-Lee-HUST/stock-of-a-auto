from __future__ import annotations

import json
import logging
import time as time_module
from dataclasses import asdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from threading import Event
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from .monitor import MonitorReport

LOG = logging.getLogger("stock_auto.service")
SHANGHAI = ZoneInfo("Asia/Shanghai")


class TradingCalendar:
    """Fail-closed exchange calendar loaded from an authorized calendar CSV.

    Required column: trade_date (YYYY-MM-DD). Only listed dates are trading days.
    The service deliberately does not infer exchange holidays from weekdays.
    """

    def __init__(self, trading_days: set[date]) -> None:
        self._days = frozenset(trading_days)

    @classmethod
    def from_csv(cls, path: str | Path) -> "TradingCalendar":
        import csv

        days: set[date] = set()
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or "trade_date" not in reader.fieldnames:
                raise ValueError("calendar CSV must contain trade_date")
            for row in reader:
                raw = (row.get("trade_date") or "").strip()
                if raw:
                    days.add(date.fromisoformat(raw))
        if not days:
            raise ValueError("trading calendar is empty; refusing to start")
        return cls(days)

    def is_trading_day(self, value: date) -> bool:
        return value in self._days


class AlertSink(Protocol):
    def publish(self, payload: dict) -> None: ...


class JsonlAlertSink:
    """Append-only local alert sink; production delivery can implement AlertSink."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def publish(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


MonitorCallback = Callable[[str, str], MonitorReport]


class MonitorService:
    """Trading-session scheduler around the existing pure MarketMonitor logic.

    The callback owns data acquisition and calls MarketMonitor.evaluate. This class
    owns session gating, retries, event de-duplication, health snapshots and shutdown.
    """

    WINDOWS = ((time(9, 20), time(9, 25)), (time(9, 30), time(11, 30)),
               (time(13, 0), time(15, 0)))

    def __init__(
        self,
        calendar: TradingCalendar,
        monitor_callback: MonitorCallback,
        alert_sink: AlertSink,
        health_path: str | Path = "runtime/health.json",
        interval_seconds: float = 5.0,
        max_backoff_seconds: float = 60.0,
    ) -> None:
        if interval_seconds <= 0 or max_backoff_seconds < interval_seconds:
            raise ValueError("invalid polling/backoff configuration")
        self.calendar = calendar
        self.monitor_callback = monitor_callback
        self.alert_sink = alert_sink
        self.health_path = Path(health_path)
        self.interval_seconds = interval_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self._seen: set[str] = set()
        self._stop = Event()
        self._last_success: str | None = None
        self._last_error: str | None = None
        self._checks = 0

    @classmethod
    def in_session(cls, current: time) -> bool:
        return any(start <= current <= end for start, end in cls.WINDOWS)

    def run_once(self, now: datetime | None = None) -> bool:
        moment = now.astimezone(SHANGHAI) if now and now.tzinfo else (now.replace(tzinfo=SHANGHAI) if now else datetime.now(SHANGHAI))
        if not self.calendar.is_trading_day(moment.date()) or not self.in_session(moment.time().replace(tzinfo=None)):
            self._write_health("idle", moment)
            return False

        trade_date = moment.date().isoformat()
        checked_at = moment.strftime("%H:%M:%S")
        try:
            report = self.monitor_callback(trade_date, checked_at)
            self._checks += 1
            for event in report.events:
                payload = {
                    "trade_date": report.trade_date,
                    "checked_at": report.checked_at,
                    "market_risk": report.market_risk,
                    "event": asdict(event),
                }
                # Ignore the polling timestamp so an unchanged signal is not re-alerted
                # every few seconds. A changed action/reason remains a distinct event.
                fingerprint_payload = {
                    "trade_date": payload["trade_date"],
                    "market_risk": payload["market_risk"],
                    "event": payload["event"],
                }
                fingerprint = json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False, default=str)
                if fingerprint not in self._seen:
                    self.alert_sink.publish(payload)
                    self._seen.add(fingerprint)
            self._last_success = moment.isoformat()
            self._last_error = None
            self._write_health("healthy", moment)
            return True
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._write_health("degraded", moment)
            LOG.exception("monitor cycle failed")
            raise

    def run_forever(self) -> None:
        backoff = self.interval_seconds
        LOG.info("monitor service started; timezone=%s", SHANGHAI.key)
        try:
            while not self._stop.is_set():
                try:
                    self.run_once()
                    backoff = self.interval_seconds
                except Exception:
                    backoff = min(max(backoff * 2, self.interval_seconds), self.max_backoff_seconds)
                self._stop.wait(backoff)
        finally:
            self._write_health("stopped", datetime.now(SHANGHAI))
            LOG.info("monitor service stopped")

    def stop(self) -> None:
        self._stop.set()

    def _write_health(self, status: str, moment: datetime) -> None:
        self.health_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": status,
            "updated_at": moment.isoformat(),
            "timezone": SHANGHAI.key,
            "checks": self._checks,
            "last_success": self._last_success,
            "last_error": self._last_error,
            "trading_day": self.calendar.is_trading_day(moment.date()),
            "in_session": self.in_session(moment.time().replace(tzinfo=None)),
        }
        temp = self.health_path.with_suffix(self.health_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.health_path)
