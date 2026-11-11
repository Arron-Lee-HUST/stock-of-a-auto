import unittest

from stock_auto.portfolio_risk import (
    PortfolioRiskManager, PortfolioRiskState, RiskLimits,
)


class PortfolioRiskTests(unittest.TestCase):
    def test_daily_loss_triggers_circuit_breaker(self):
        state = PortfolioRiskState(98000, 100000, 105000, 20000)
        decision = PortfolioRiskManager().assess(state)
        self.assertFalse(decision.allow_new_positions)
        self.assertTrue(any("日内亏损" in x for x in decision.reasons))

    def test_sector_concentration_blocks_new_position(self):
        state = PortfolioRiskState(100000, 100000, 100000, 20000,
                                   sector_exposure={"AI": 30000})
        decision = PortfolioRiskManager().assess(state, "AI", 10000)
        self.assertFalse(decision.allow_new_positions)

    def test_cautious_market_reduces_remaining_exposure(self):
        state = PortfolioRiskState(100000, 100000, 100000, 10000,
                                   market_risk_level="cautious")
        decision = PortfolioRiskManager().assess(state)
        self.assertTrue(decision.allow_new_positions)
        self.assertEqual(decision.exposure_limit_pct, 30)


if __name__ == "__main__":
    unittest.main()
