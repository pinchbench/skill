"""
RunTrendAnalyzer — detect score regression across sequential benchmark runs.

Analyzes results JSON files written by benchmark.py to detect whether a model's
performance is improving, stable, or degrading over time via OLS slope fitting.
"""
import json
import logging
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("benchmark")


@dataclass
class RunPoint:
    """A single data point from a benchmark run."""
    run_id: str
    timestamp: float
    model: str
    score_pct: float
    task_count: int


@dataclass
class RunTrendReport:
    """Trend analysis report for a single model."""
    model: str
    run_count: int
    window: int
    slope: float
    points: List[RunPoint]
    regression_detected: bool
    regression_threshold: float
    task_count_varies: bool = False

    def summary(self) -> str:
        """Return a CLI-friendly summary string."""
        direction = (
            "▼ REGRESSION"
            if self.regression_detected
            else "▲ improving"
            if self.slope > 0
            else "→ stable"
        )
        note = (
            " ⚠ task count varied — slope may reflect suite changes"
            if self.task_count_varies
            else ""
        )
        return (
            f"{direction}: {self.model} slope={self.slope:+.2f}%/run "
            f"over last {self.run_count} runs "
            f"(threshold={self.regression_threshold:+.2f}){note}"
        )


class RunTrendAnalyzer:
    """Detect performance regression across sequential benchmark runs."""

    def __init__(
        self,
        results_dir: Path,
        window: int = 10,
        regression_threshold: float = -0.5,
    ):
        """
        Args:
            results_dir: Directory containing benchmark result JSON files.
            window: Number of most recent runs to analyze.
            regression_threshold: Slope (pct/run) below which regression is flagged.
        """
        self.results_dir = results_dir
        self.window = window
        self.regression_threshold = regression_threshold

    def load_points(self, model: Optional[str] = None) -> Dict[str, List[RunPoint]]:
        """
        Load and group RunPoint data from result JSON files, keyed by model slug.
        Skips files that fail to parse (JSONDecodeError, OSError).
        """
        grouped: Dict[str, List[RunPoint]] = {}
        for path in sorted(self.results_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            # Skip incomplete runs (written incrementally during benchmark)
            if data.get("in_progress"):
                continue

            m = data.get("model", "")
            ts = data.get("timestamp", 0.0)
            run_id = data.get("run_id", path.stem)
            tasks = data.get("tasks", [])
            if not tasks:
                continue

            total = sum(
                t["grading"]["mean"]
                for t in tasks
                if "grading" in t
            )
            score_pct = (total / len(tasks)) * 100

            if model and m != model:
                continue

            grouped.setdefault(m, []).append(
                RunPoint(run_id, ts, m, score_pct, len(tasks))
            )

        for pts in grouped.values():
            pts.sort(key=lambda p: p.timestamp)

        return grouped

    def analyze(
        self, model: Optional[str] = None
    ) -> List[RunTrendReport]:
        """
        Run OLS slope analysis per model over the configured window.
        Returns a list of RunTrendReport, sorted by slope ascending.
        """
        grouped = self.load_points(model)
        reports: List[RunTrendReport] = []

        for m, pts in grouped.items():
            window_pts = pts[-self.window:]
            if len(window_pts) < 2:
                continue

            xs = list(range(len(window_pts)))
            ys = [p.score_pct for p in window_pts]
            slope, intercept = statistics.linear_regression(xs, ys)

            task_counts = {p.task_count for p in window_pts}
            task_count_varies = len(task_counts) > 1

            reports.append(
                RunTrendReport(
                    model=m,
                    run_count=len(window_pts),
                    window=self.window,
                    slope=slope,
                    points=window_pts,
                    regression_detected=slope < self.regression_threshold,
                    regression_threshold=self.regression_threshold,
                    task_count_varies=task_count_varies,
                )
            )

        reports.sort(key=lambda r: r.slope)
        return reports

    def run(self, model: Optional[str] = None) -> None:
        """CLI entry: analyze and print results."""
        reports = self.analyze(model)
        if not reports:
            logger.info("No trend data available (need ≥2 runs per model).")
            return

        logger.info("\n" + "=" * 80)
        logger.info("📈 RUN TREND ANALYSIS")
        logger.info("=" * 80)

        for report in reports:
            logger.info("   %s", report.summary())

            # Show recent scores
            for p in report.points:
                logger.info("     %s: %.1f%% (%d tasks)", p.run_id, p.score_pct, p.task_count)

        logger.info("%s", "=" * 80)
