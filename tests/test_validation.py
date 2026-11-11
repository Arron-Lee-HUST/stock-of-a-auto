import unittest

from stock_auto.data import DailyBar
from stock_auto.validation import validate_bars


class ValidationTests(unittest.TestCase):
    def test_duplicate_and_unsorted_keys_are_reported(self):
        a = DailyBar("sh600000", "2024-01-03", 10, 11, 9, 10, 1000)
        b = DailyBar("sh600000", "2024-01-02", 10, 11, 9, 10, 1000)
        report = validate_bars([a, b, a])
        self.assertFalse(report.valid)
        self.assertTrue(report.duplicate_keys)
        self.assertTrue(report.unsorted_keys)


if __name__ == "__main__":
    unittest.main()
