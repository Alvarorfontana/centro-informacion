import unittest

from engine import metrics, run_experiment, rolling_origin_backtest


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"periodo": str(i), "produccion": str(10 + 2 * i), "energia": str(3 + i)}
            for i in range(30)
        ]

    def test_temporal_holdout(self):
        result = run_experiment(self.rows, "produccion", ["energia"])
        self.assertEqual(result["status"], "completed")
        self.assertGreater(result["test_observations"], 0)
        self.assertIn("ridge", result["models"])
        self.assertIn("persistence", result["models"])

    def test_backtest(self):
        result = rolling_origin_backtest(self.rows, "produccion", ["energia"], min_train=8)
        self.assertGreater(len(result["folds"]), 0)
        self.assertGreaterEqual(result["mean_rmse"], 0)

    def test_metrics(self):
        result = metrics([1, 2, 3], [1, 2, 4])
        self.assertAlmostEqual(result["mae"], 1 / 3)
        self.assertAlmostEqual(result["rmse"], (1 / 3) ** 0.5)

    def test_rejects_short_series(self):
        with self.assertRaises(ValueError):
            run_experiment(self.rows[:5], "produccion", ["energia"])


if __name__ == "__main__":
    unittest.main()
