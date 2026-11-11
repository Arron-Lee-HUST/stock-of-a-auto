import csv
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_auto.monitor import MonitorEvent, MonitorReport
from stock_auto.service import JsonlAlertSink, MonitorService, TradingCalendar


class ServiceTests(unittest.TestCase):
    def test_calendar_fails_closed_for_unlisted_date(self):
        calendar = TradingCalendar({date(2026, 11, 11)})
        self.assertTrue(calendar.is_trading_day(date(2026, 11, 11)))
        self.assertFalse(calendar.is_trading_day(date(2026, 11, 12)))

    def test_calendar_csv_requires_trade_date_and_nonempty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calendar.csv"
            path.write_text("trade_date\n2026-11-11\n", encoding="utf-8")
            self.assertTrue(TradingCalendar.from_csv(path).is_trading_day(date(2026, 11, 11)))
            path.write_text("wrong\n2026-11-11\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                TradingCalendar.from_csv(path)

    def test_run_once_is_session_gated_and_writes_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            called = []
            report = MonitorReport("2026-11-11", "09:23:00", "normal",
                                   [MonitorEvent("sh600000", "auction", "watch")])
            service = MonitorService(
                TradingCalendar({date(2026, 11, 11)}),
                lambda d, t: called.append((d, t)) or report,
                JsonlAlertSink(root / "alerts.jsonl"),
                root / "health.json",
            )
            outside = datetime(2026, 11, 11, 8, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
            self.assertFalse(service.run_once(outside))
            self.assertEqual(called, [])
            inside = datetime(2026, 11, 11, 9, 23, tzinfo=ZoneInfo("Asia/Shanghai"))
            self.assertTrue(service.run_once(inside))
            self.assertEqual(len(called), 1)
            health = json.loads((root / "health.json").read_text(encoding="utf-8"))
            self.assertEqual(health["status"], "healthy")
            self.assertEqual(health["timezone"], "Asia/Shanghai")
            lines = (root / "alerts.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)

    def test_identical_events_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = MonitorReport("2026-11-11", "09:23:00", "normal",
                                   [MonitorEvent("sh600000", "auction", "watch")])
            service = MonitorService(TradingCalendar({date(2026, 11, 11)}),
                lambda d, t: report, JsonlAlertSink(root / "alerts.jsonl"), root / "health.json")
            moment = datetime(2026, 11, 11, 9, 23, tzinfo=ZoneInfo("Asia/Shanghai"))
            service.run_once(moment)
            service.run_once(moment)
            self.assertEqual(len((root / "alerts.jsonl").read_text().splitlines()), 1)

    def test_weekend_or_holiday_does_not_call_monitor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            called = []
            service = MonitorService(TradingCalendar(set()),
                lambda d, t: called.append(True), JsonlAlertSink(root / "alerts.jsonl"),
                root / "health.json")
            self.assertFalse(service.run_once(datetime(2026, 11, 11, 9, 23)))
            self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
