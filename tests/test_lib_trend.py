"""Tests for lib_trend — RunTrendAnalyzer."""
import json
import tempfile
import time
from pathlib import Path
from unittest import TestCase

from scripts.lib_trend import RunTrendAnalyzer, RunTrendReport


class TestRunTrendAnalyzer(TestCase):
    def _write_run(self, run_dir: Path, run_id: str, model: str, scores: list):
        """Helper: each score = one task's grading.mean in the result JSON."""
        tasks = [
            {"task_id": f"task_{i}", "grading": {"mean": s}}
            for i, s in enumerate(scores)
        ]
        data = {
            "model": model,
            "run_id": run_id,
            "timestamp": time.time(),
            "suite": "all",
            "tasks": tasks,
        }
        (run_dir / f"{run_id}_{model.replace('/', '_')}.json").write_text(json.dumps(data))

    def test_no_data_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            analyzer = RunTrendAnalyzer(Path(tmp))
            self.assertEqual(analyzer.analyze(), [])

    def test_single_run_returns_empty(self):
        """Need >= 2 runs for trend analysis."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, "0001", "claude", [0.8])
            analyzer = RunTrendAnalyzer(run_dir)
            self.assertEqual(analyzer.analyze(), [])

    def test_regression_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            # Declining overall scores: 4 runs, single-task each
            for i, score in enumerate([0.9, 0.85, 0.80, 0.75]):
                self._write_run(run_dir, f"{i:04d}", "claude-sonnet", [score])
            analyzer = RunTrendAnalyzer(run_dir, window=10, regression_threshold=-0.5)
            reports = analyzer.analyze()
            self.assertEqual(len(reports), 1)
            self.assertTrue(reports[0].regression_detected)
            self.assertLess(reports[0].slope, -0.5)

    def test_improving_not_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            for i, score in enumerate([0.75, 0.80, 0.85, 0.90]):
                self._write_run(run_dir, f"{i:04d}", "gpt", [score])
            analyzer = RunTrendAnalyzer(run_dir)
            reports = analyzer.analyze()
            self.assertEqual(len(reports), 1)
            self.assertFalse(reports[0].regression_detected)
            self.assertGreater(reports[0].slope, 0)

    def test_malformed_file_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "bad.json").write_text("{INVALID JSON!")
            self._write_run(run_dir, "0001", "model-a", [0.8])
            self._write_run(run_dir, "0002", "model-a", [0.9])
            analyzer = RunTrendAnalyzer(run_dir)
            reports = analyzer.analyze()
            self.assertEqual(len(reports), 1)

    def test_task_count_varies_flag(self):
        """Suite expansion across runs should set task_count_varies."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, "0001", "claude", [0.9])          # 1 task
            self._write_run(run_dir, "0002", "claude", [0.85, 0.88, 0.90])  # 3 tasks
            analyzer = RunTrendAnalyzer(run_dir)
            reports = analyzer.analyze()
            self.assertEqual(len(reports), 1)
            self.assertTrue(reports[0].task_count_varies)

    def test_task_count_varies_false_when_equal(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, "0001", "claude", [0.9, 0.8])
            self._write_run(run_dir, "0002", "claude", [0.85, 0.88])
            analyzer = RunTrendAnalyzer(run_dir)
            reports = analyzer.analyze()
            self.assertEqual(len(reports), 1)
            self.assertFalse(reports[0].task_count_varies)

    def test_summary_string_regression(self):
        report = RunTrendReport(
            model="claude-sonnet",
            run_count=5,
            window=10,
            slope=-1.2,
            points=[],
            regression_detected=True,
            regression_threshold=-0.5,
            task_count_varies=False,
        )
        summary = report.summary()
        self.assertIn("REGRESSION", summary)
        self.assertIn("-1.20", summary)

    def test_summary_string_task_count_warning(self):
        report = RunTrendReport(
            model="gpt-4",
            run_count=4,
            window=10,
            slope=-0.8,
            points=[],
            regression_detected=True,
            regression_threshold=-0.5,
            task_count_varies=True,
        )
        summary = report.summary()
        self.assertIn("task count varied", summary)

    def test_stable_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            for i, score in enumerate([0.80, 0.80, 0.80, 0.80]):
                self._write_run(run_dir, f"{i:04d}", "stable-model", [score])
            analyzer = RunTrendAnalyzer(run_dir)
            reports = analyzer.analyze()
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].slope, 0.0)
            self.assertFalse(reports[0].regression_detected)

    def test_multiple_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, "0001", "claude", [0.9])
            self._write_run(run_dir, "0002", "claude", [0.8])
            self._write_run(run_dir, "0003", "gpt", [0.7])
            self._write_run(run_dir, "0004", "gpt", [0.75])
            analyzer = RunTrendAnalyzer(run_dir)
            reports = analyzer.analyze()
            self.assertEqual(len(reports), 2)
            # Sorted by slope ascending
            self.assertEqual(reports[0].model, "claude")
            self.assertLess(reports[0].slope, 0)
            self.assertEqual(reports[1].model, "gpt")
            self.assertGreater(reports[1].slope, 0)

    def test_filter_by_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, "0001", "claude", [0.9])
            self._write_run(run_dir, "0002", "claude", [0.8])
            self._write_run(run_dir, "0003", "gpt", [0.7])
            self._write_run(run_dir, "0004", "gpt", [0.75])
            analyzer = RunTrendAnalyzer(run_dir)
            reports = analyzer.analyze(model="claude")
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].model, "claude")
