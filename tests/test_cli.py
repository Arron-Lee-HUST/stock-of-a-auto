import unittest

from stock_auto.cli import main


class CliTests(unittest.TestCase):
    def test_help_returns_zero(self):
        with self.assertRaises(SystemExit) as raised:
            main(["--help"])
        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
