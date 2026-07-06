"""Post-earnings price direction model.

Logistic regression (pure numpy, no sklearn dependency) mapping
announcement-level NLP features to the sign of the next-N-day return.

Features per announcement:
    0. ensemble document sentiment score in [-1, 1]
    1. mean sentiment of forward-looking statements
    2. fraction of sentences routed to XLM-R (code-switch intensity)
    3. FLS density (FLS count / sentence count)
"""

from dataclasses import dataclass

import numpy as np

N_FEATURES = 4


@dataclass
class DirectionModel:
    weights: np.ndarray  # shape (N_FEATURES + 1,), last term is bias

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Xb = np.hstack([X, np.ones((X.shape[0], 1))])
        z = Xb @ self.weights
        return 1.0 / (1.0 + np.exp(-z))

    def predict(self, X: np.ndarray) -> np.ndarray:
        """1 = up, 0 = down."""
        return (self.predict_proba(X) >= 0.5).astype(int)


def train(
    X: np.ndarray,
    y: np.ndarray,
    lr: float = 0.1,
    epochs: int = 2000,
    l2: float = 1e-3,
    seed: int = 7,
) -> DirectionModel:
    """Batch gradient-descent logistic regression."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if X.ndim != 2 or X.shape[1] != N_FEATURES:
        raise ValueError(f"X must be (n, {N_FEATURES})")
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    rng = np.random.default_rng(seed)
    w = rng.normal(scale=0.01, size=Xb.shape[1])
    n = Xb.shape[0]
    for _ in range(epochs):
        p = 1.0 / (1.0 + np.exp(-(Xb @ w)))
        grad = Xb.T @ (p - y) / n + l2 * w
        w -= lr * grad
    return DirectionModel(weights=w)


def directional_accuracy(model: DirectionModel, X: np.ndarray, y: np.ndarray) -> float:
    return float((model.predict(np.asarray(X, dtype=float)) == np.asarray(y)).mean())
