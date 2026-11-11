from .config import StrategyConfig
from .models import MarketSnapshot, Signal
from .scoring import score_snapshot


def evaluate_candidate(snapshot: MarketSnapshot, config: StrategyConfig | None = None) -> Signal:
    """Single entry point for after-close candidate screening."""
    return score_snapshot(snapshot, config)
