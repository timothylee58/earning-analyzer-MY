import numpy as np
from django.test import TestCase

from .backtest import run_backtest
from .direction import directional_accuracy, train
from .fls import extract_fls, is_fls


class FlsTests(TestCase):
    def test_english_guidance_is_fls(self):
        self.assertTrue(
            is_fls("The Group expects revenue to grow in the next financial year.")
        )

    def test_bm_guidance_is_fls(self):
        self.assertTrue(
            is_fls("Kumpulan menjangka margin akan terus meningkat pada FY2027.")
        )

    def test_historical_statement_is_not_fls(self):
        self.assertFalse(is_fls("Revenue for the quarter was RM45.2 million."))

    def test_safe_harbor_boilerplate_excluded(self):
        self.assertFalse(
            is_fls(
                "Forward-looking statements are subject to risks; do not place "
                "undue reliance on such statements."
            )
        )

    def test_extract_from_document(self):
        text = (
            "Revenue was RM10 million. "
            "Management remains optimistic going forward. "
            "Dividen sebanyak 2 sen telah diisytiharkan."
        )
        fls = extract_fls(text)
        self.assertEqual(len(fls), 1)
        self.assertIn("optimistic", fls[0])


class DirectionModelTests(TestCase):
    def _synthetic(self, n=400, seed=3):
        rng = np.random.default_rng(seed)
        X = rng.normal(size=(n, 4))
        # Direction driven mostly by doc sentiment + FLS sentiment, with noise.
        logits = 2.5 * X[:, 0] + 1.5 * X[:, 1] + rng.normal(scale=0.5, size=n)
        y = (logits > 0).astype(int)
        return X, y

    def test_learns_synthetic_signal(self):
        X, y = self._synthetic()
        model = train(X, y)
        acc = directional_accuracy(model, X, y)
        self.assertGreaterEqual(acc, 0.85)

    def test_rejects_bad_shape(self):
        with self.assertRaises(ValueError):
            train(np.zeros((10, 2)), np.zeros(10))

    def test_predict_proba_bounds(self):
        X, y = self._synthetic(n=50)
        model = train(X, y, epochs=200)
        p = model.predict_proba(X)
        self.assertTrue(((p >= 0) & (p <= 1)).all())


class BacktestTests(TestCase):
    def test_perfect_signal_has_positive_sharpe(self):
        rng = np.random.default_rng(11)
        X = rng.normal(size=(200, 4))
        logits = 3.0 * X[:, 0]
        y = (logits > 0).astype(int)
        model = train(X, y)
        # Returns aligned with the true direction.
        returns = np.where(y == 1, 1.0, -1.0) * np.abs(rng.normal(0.02, 0.01, 200))
        result = run_backtest(model, X, returns)
        self.assertGreater(result.hit_rate, 0.8)
        self.assertGreater(result.sharpe, 0.8)

    def test_empty_backtest(self):
        model = train(np.random.default_rng(0).normal(size=(20, 4)), np.zeros(20))
        result = run_backtest(model, np.zeros((0, 4)), np.zeros(0))
        self.assertEqual(result.n_trades, 0)
        self.assertEqual(result.sharpe, 0.0)

    def test_length_mismatch_raises(self):
        model = train(np.random.default_rng(0).normal(size=(20, 4)), np.ones(20))
        with self.assertRaises(ValueError):
            run_backtest(model, np.zeros((5, 4)), np.zeros(4))
