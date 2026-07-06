"""Event-driven backtest for the post-earnings direction signal.

Strategy: at each earnings announcement, go long when the model predicts up,
short when it predicts down, hold for the event window. Reports hit rate and
annualised Sharpe (success metric: Sharpe >= 0.8).
"""

from dataclasses import dataclass

import numpy as np

from .direction import DirectionModel

TRADING_DAYS = 252


@dataclass
class BacktestResult:
    n_trades: int
    hit_rate: float
    mean_return: float
    sharpe: float

    def as_dict(self) -> dict:
        return {
            "n_trades": self.n_trades,
            "hit_rate": round(self.hit_rate, 4),
            "mean_return": round(self.mean_return, 6),
            "sharpe": round(self.sharpe, 4),
        }


def run_backtest(
    model: DirectionModel,
    X: np.ndarray,
    event_returns: np.ndarray,
    holding_days: int = 5,
) -> BacktestResult:
    """X: (n, features) per announcement; event_returns: realised return over
    the holding window following each announcement."""
    X = np.asarray(X, dtype=float)
    r = np.asarray(event_returns, dtype=float)
    if len(r) != X.shape[0]:
        raise ValueError("X and event_returns length mismatch")
    if len(r) == 0:
        return BacktestResult(0, 0.0, 0.0, 0.0)

    side = np.where(model.predict(X) == 1, 1.0, -1.0)
    pnl = side * r
    hit_rate = float((pnl > 0).mean())
    mean_ret = float(pnl.mean())
    std = float(pnl.std(ddof=1)) if len(pnl) > 1 else 0.0
    if std == 0.0:
        sharpe = 0.0
    else:
        # Annualise per-event returns by holding period.
        periods_per_year = TRADING_DAYS / holding_days
        sharpe = mean_ret / std * float(np.sqrt(periods_per_year))
    return BacktestResult(len(pnl), hit_rate, mean_ret, sharpe)
