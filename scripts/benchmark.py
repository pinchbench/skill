#!/usr/bin/env python3
"""
PinchBench - OpenClaw Agent Benchmarking System

This script orchestrates benchmarking of OpenClaw agents using tasks loaded
from the tasks/ directory.
"""
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0.1",
# ]
# ///

import argparse
import importlib.metadata
import json
import logging
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Any

from lib_agent import (
    cleanup_agent_sessions,
    ensure_agent_exists,
    execute_openclaw_task,
    ModelValidationError,
    slugify_model,
    validate_openrouter_model,
)
from lib_axiom import init_axiom
from lib_grading import (
    DEFAULT_JUDGE_TIMEOUT_SECONDS,
    GradeResult,
    grade_task,
    set_judge_cache_dir,
    get_judge_cache_stats,
    clear_judge_cache,
)
from lib_tasks import Task, TaskLoader


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("benchmark.log")],
)

logger = logging.getLogger("benchmark")


class OpenClawAgent:
    """Scaffold for OpenClaw agent creation and execution."""

    def __init__(self, agent_id: str, config: Optional[Dict[str, Any]] = None):
        self.agent_id = agent_id
        self.config = config or {}
        logger.info(f"Initialized OpenClawAgent: {agent_id}")

    def execute_task(self, task: Task, simulate: bool = False) -> Dict[str, Any]:
        """
        Execute a task with this agent.

        Args:
            task: The Task object to execute
            simulate: If True, simulates execution for demonstration

        Returns:
            Dictionary containing execution results
        """
        if simulate:
            logger.info("Simulate flag no longer supported for execute_task")
        raise NotImplementedError("Use execute_openclaw_task helper for real runs")


class BenchmarkRunner:
    """Orchestrates benchmark execution across tasks and agents."""

    def __init__(self, tasks_dir: Path):
        self.task_loader = TaskLoader(tasks_dir)
        self.tasks: List[Task] = []
        self.agents: List[OpenClawAgent] = []
        logger.info("Initialized BenchmarkRunner")

    def load_tasks(self) -> None:
        """Load all tasks from the tasks directory."""
        logger.info("Loading tasks...")
        self.tasks = self.task_loader.load_all_tasks()
        logger.info(f"Loaded {len(self.tasks)} tasks")

    def create_agent(self, agent_id: str, config: Optional[Dict[str, Any]] = None) -> OpenClawAgent:
        """
        Create a new OpenClaw agent for benchmarking.

        Args:
            agent_id: Unique identifier for the agent
            config: Optional configuration dictionary

        Returns:
            OpenClawAgent instance
        """
        logger.info(f"Creating agent: {agent_id}")
        agent = OpenClawAgent(agent_id, config)
        self.agents.append(agent)
        return agent

    def run_benchmark(
        self, agent: OpenClawAgent, task_ids: Optional[List[str]] = None, simulate: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Run benchmark for an agent on specified tasks.

        Args:
            agent: The OpenClawAgent to benchmark
            task_ids: Optional list of task IDs to run. If None, runs all tasks.
            simulate: If True, simulates execution for demonstration

        Returns:
            List of result dictionaries
        """
        # Filter tasks if specific IDs provided
        if task_ids:
            tasks_to_run = [t for t in self.tasks if t.task_id in task_ids]
            logger.info(f"🎯 Running benchmark on {len(tasks_to_run)} specified tasks")
        else:
            tasks_to_run = self.tasks
            logger.info(f"🎯 Running benchmark on all {len(tasks_to_run)} tasks")

        results = []
        for i, task in enumerate(tasks_to_run, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"📋 Task {i}/{len(tasks_to_run)}")
            logger.info(f"{'=' * 80}")
            result = agent.execute_task(task, simulate=simulate)
            results.append(result)

        logger.info(f"\n{'=' * 80}")
        logger.info(f"✨ Benchmark complete! Executed {len(results)} tasks")
        logger.info(f"{'=' * 80}")

        # Print summary
        total_time = sum(r["execution_time"] for r in results)
        logger.info("\n📊 BENCHMARK SUMMARY")
        logger.info(f"   Agent: {agent.agent_id}")
        logger.info(f"   Tasks completed: {len(results)}")
        logger.info(f"   Total execution time: {total_time:.2f}s")
        logger.info(f"   Average time per task: {total_time / len(results):.2f}s")

        return results

    def print_task_summary(self) -> None:
        """Print a summary of all loaded tasks."""
        if not self.tasks:
            logger.warning("No tasks loaded")
            return

        print("\n" + "=" * 80)
        print(f"LOADED TASKS SUMMARY ({len(self.tasks)} tasks)")
        print("=" * 80)

        for task in self.tasks:
            print(f"\n[{task.task_id}] {task.name}")
            print(f"  Category: {task.category}")
            print(f"  Grading: {task.grading_type}")
            print(f"  Timeout: {task.timeout_seconds}s")
            print(f"  Criteria: {len(task.grading_criteria)} items")
            print(
                f"  Prompt: {task.prompt[:100]}..."
                if len(task.prompt) > 100
                else f"  Prompt: {task.prompt}"
            )

        print("\n" + "=" * 80)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PinchBench OpenClaw Benchmark Runner")
    parser.add_argument(
        "--model",
        required=False,
        help="Model identifier (e.g., anthropic/claude-sonnet-4)",
    )
    parser.add_argument(
        "--suite",
        default="all",
        help='Tasks to run: "all", "automated-only", a category name (e.g. "coding"), or comma-separated task IDs',
    )
    parser.add_argument(
        "--core",
        action="store_true",
        help="Run only core tasks (~25 representative tasks for quick benchmarking)",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Results directory",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Request a new API token and save it to local config",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip uploading to server",
    )
    parser.add_argument(
        "--upload",
        type=str,
        metavar="RESULTS_JSON",
        help="Upload a previous run's results JSON and exit (skips benchmarking)",
    )
    parser.add_argument(
        "--timeout-multiplier",
        type=float,
        default=1.0,
        help="Scale all task timeouts",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs per task for averaging",
    )
    parser.add_argument(
        "--judge",
        default=None,
        help=(
            "Judge model or backend. Default (unset): OpenClaw agent session with "
            "openrouter/anthropic/claude-opus-4.5. Set to a model ID to call its API "
            "directly (e.g. openai/gpt-4o, anthropic/claude-sonnet-4-5-20250514, claude)"
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Custom OpenAI-compatible API base URL (bypasses OpenRouter validation)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for custom endpoint (default: $OPENAI_API_KEY env var)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (shows transcript contents, workspace files, etc.)",
    )
    parser.add_argument(
        "--official-key",
        type=str,
        metavar="KEY",
        help="Official key to mark submission as official (can also use PINCHBENCH_OFFICIAL_KEY env var)",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Continue running all tasks even if sanity check scores 0%%",
    )
    parser.add_argument(
        "--no-parallel-judge",
        action="store_true",
        help="Disable parallel judge execution (grade synchronously after each task)",
    )
    parser.add_argument(
        "--no-judge-cache",
        action="store_true",
        help="Disable judge result caching (re-grade even if transcript+rubric unchanged)",
    )
    parser.add_argument(
        "--clear-judge-cache",
        action="store_true",
        help="Clear the judge cache before running",
    )
    parser.add_argument(
        "--trend",
        action="store_true",
        help="Run trend analysis after benchmark completes (requires ≥2 runs in output dir)",
    )
    parser.add_argument(
        "--trend-window",
        type=int,
        default=10,
        metavar="N",
        help="Number of recent runs to include in trend analysis (default: 10)",
    )
    parser.add_argument(
        "--trend-threshold",
        type=float,
        default=-0.5,
        help="Slope (%%/run) below which regression is flagged (default: -0.5)",
    )
    args = parser.parse_args()

    # Validate --trend-window
    if args.trend_window < 2:
        parser.error("--trend-window must be >= 2")

    return args


def _select_task_ids(
    tasks: List[Task],
    suite: str,
    category_map: Optional[Dict[str, str]] = None,
) -> Optional[List[str]]:
    if suite == "all":
        return None
    if suite == "automated-only":
        return [task.task_id for task in tasks if task.grading_type == "automated"]

    # Check if suite matches a manifest category name
    if category_map:
        available_categories = set(category_map.values())
        # Support "+" syntax for combining categories: "coding+research"
        requested = [s.strip() for s in suite.split("+")]
        if all(r in available_categories for r in requested):
            requested_set = set(requested)
            return [
                task.task_id for task in tasks if category_map.get(task.task_id) in requested_set
            ]

    # Fall back to comma-separated task IDs
    return [task_id.strip() for task_id in suite.split(",") if task_id.strip()]


def _next_run_id(run_root: Path) -> str:
    run_root.mkdir(parents=True, exist_ok=True)
    existing = []
    for entry in run_root.iterdir():
        if entry.is_dir() and entry.name.isdigit():
            existing.append(int(entry.name))
    next_id = (max(existing) + 1) if existing else 1
    return f"{next_id:04d}"


def _load_ascii_art(script_dir: Path, filename: str) -> str | None:
    """Load ASCII art from a local file if available."""
    art_path = script_dir / filename
    try:
        return art_path.read_text(encoding="utf-8").rstrip("\n")
    except FileNotFoundError:
        return None


def _supports_truecolor() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _get_benchmark_version(script_dir: Path) -> str:
    try:
        return importlib.metadata.version("pinchbench")
    except Exception:
        pass

    version_file = script_dir / "BENCHMARK_VERSION"
    if version_file.is_file():
        try:
            return version_file.read_text().strip()
        except Exception:
            pass

    def _split_semver(tag: str) -> Optional[tuple[int, int, int]]:
        cleaned = tag.strip()
        if cleaned.startswith("v"):
            cleaned = cleaned[1:]
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", cleaned)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2)), int(match.group(3))

    try:
        result = subprocess.run(
            [
                "git",
                "describe",
                "--tags",
                "--long",
                "--match",
                "v[0-9]*.[0-9]*.[0-9]*",
                "--match",
                "[0-9]*.[0-9]*.[0-9]*",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            cwd=script_dir,
        )
        if result.returncode == 0:
            described = result.stdout.strip()
            describe_match = re.match(r"^(.+)-(\d+)-g([0-9a-fA-F]+)$", described)
            if describe_match:
                raw_tag = describe_match.group(1)
                commit_distance = int(describe_match.group(2))
                short_sha = describe_match.group(3)
                parsed_tag = _split_semver(raw_tag)
                if parsed_tag is not None:
                    major, minor, patch = parsed_tag
                    if commit_distance == 0:
                        return f"{major}.{minor}.{patch}"
                    next_patch = patch + 1
                    return f"{major}.{minor}.{next_patch}-dev.{commit_distance}+g{short_sha}"
            if described:
                return described
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            cwd=script_dir,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _colorize_gradient(ascii_art: str) -> str:
    if not _supports_truecolor():
        return ascii_art
    lines = ascii_art.splitlines()
    if not lines:
        return ascii_art
    last_index = max(len(lines) - 1, 1)
    colored_lines = []
    for idx, line in enumerate(lines):
        t = idx / last_index
        green_blue = int(255 * (1 - t))
        colored_lines.append(f"\x1b[38;2;255;{green_blue};{green_blue}m{line}\x1b[0m")
    return "\n".join(colored_lines)


def _compute_efficiency_summary(
    task_entries: List[Dict[str, Any]],
    grades_by_task_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute aggregate token efficiency metrics across all tasks.

    Returns a dict with total token usage, cost, and efficiency ratios
    (score per token, score per dollar) so that different models can be
    compared not just on quality but also on resource consumption.
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    total_cost_usd = 0.0
    total_requests = 0
    total_execution_time = 0.0
    tasks_with_usage = 0

    per_task_efficiency: List[Dict[str, Any]] = []
    for entry in task_entries:
        usage = entry.get("usage", {})
        task_id = entry["task_id"]
        grading = grades_by_task_id.get(task_id, {})
        score = float(grading.get("mean", 0.0))

        inp = int(usage.get("input_tokens", 0))
        out = int(usage.get("output_tokens", 0))
        tot = int(usage.get("total_tokens", 0))
        cost = float(usage.get("cost_usd", 0.0) or 0.0)
        reqs = int(usage.get("request_count", 0))
        exec_time = float(entry.get("execution_time", 0.0) or 0.0)

        total_input_tokens += inp
        total_output_tokens += out
        total_tokens += tot
        total_cost_usd += cost
        total_requests += reqs
        total_execution_time += exec_time

        if tot > 0:
            tasks_with_usage += 1

        per_task_efficiency.append(
            {
                "task_id": task_id,
                "score": round(score, 4),
                "total_tokens": tot,
                "cost_usd": round(cost, 6),
                "tokens_per_score_point": round(tot / score, 1) if score > 0 else None,
            }
        )

    # Aggregate scores
    all_scores = [float(g.get("mean", 0.0)) for g in grades_by_task_id.values()]
    total_score = sum(all_scores)
    num_tasks = len(all_scores)

    summary: Dict[str, Any] = {
        "total_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "total_requests": total_requests,
        "total_execution_time_seconds": round(total_execution_time, 2),
        "tasks_with_usage_data": tasks_with_usage,
        "tokens_per_task": round(total_tokens / num_tasks, 1) if num_tasks > 0 else 0,
        "cost_per_task_usd": round(total_cost_usd / num_tasks, 6) if num_tasks > 0 else 0,
        "score_per_1k_tokens": (
            round(total_score / (total_tokens / 1000), 6) if total_tokens > 0 else None
        ),
        "score_per_dollar": (
            round(total_score / total_cost_usd, 4) if total_cost_usd > 0 else None
        ),
        "per_task": per_task_efficiency,
    }
    return summary


def _log_efficiency_summary(
    efficiency: Dict[str, Any],
    grades_by_task_id: Dict[str, Dict[str, Any]],
) -> None:
    """Log a human-readable token efficiency summary."""
    all_scores = [float(g.get("mean", 0.0)) for g in grades_by_task_id.values()]
    mean_score = statistics.mean(all_scores) if all_scores else 0.0

    logger.info("\n%s", "=" * 80)
    logger.info("📊 TOKEN EFFICIENCY SUMMARY")
    logger.info("%s", "=" * 80)
    logger.info(
        "   Total tokens used: %s (input: %s, output: %s)",
        f"{efficiency['total_tokens']:,}",
        f"{efficiency['total_input_tokens']:,}",
        f"{efficiency['total_output_tokens']:,}",
    )
    logger.info("   Total API requests: %s", f"{efficiency['total_requests']:,}")
    if efficiency["total_cost_usd"] > 0:
        logger.info("   Total cost: $%.4f", efficiency["total_cost_usd"])
    logger.info(
        "   Avg tokens/task: %s",
        f"{efficiency['tokens_per_task']:,.0f}",
    )
    logger.info("   Mean score: %.4f", mean_score)
    if efficiency.get("score_per_1k_tokens") is not None:
        logger.info(
            "   Score per 1K tokens: %.4f (higher = more efficient)",
            efficiency["score_per_1k_tokens"],
        )
    if efficiency.get("score_per_dollar") is not None:
        logger.info(
            "   Score per dollar: %.4f (higher = more cost-efficient)",
            efficiency["score_per_dollar"],
        )
    logger.info("%s", "=" * 80)


def _compute_category_scores(
    task_entries: List[Dict[str, Any]],
    tasks_by_id: Dict[str, Any],
    category_order: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compute per-category score rollups from task results.

    Returns a dict mapping category name to a dict with keys:
    ``score``, ``max_score``, ``pct``, ``task_count``.

    If *category_order* is provided it is used only for ordering the returned
    dict (Python 3.7+ preserves insertion order).  Categories not in the order
    list are appended alphabetically.
    """
    raw: Dict[str, Dict[str, float]] = {}

    for entry in task_entries:
        task_id = entry["task_id"]
        task = tasks_by_id.get(task_id)
        if not task:
            continue

        category = task.category.upper() if task.category else "UNCATEGORIZED"
        grading = entry.get("grading", {})
        mean_score = float(grading.get("mean", 0.0))
        max_score = 1.0  # Each task is scored 0-1

        if category not in raw:
            raw[category] = {"score": 0.0, "max_score": 0.0, "task_count": 0}

        raw[category]["score"] += mean_score
        raw[category]["max_score"] += max_score
        raw[category]["task_count"] += 1

    # Determine display order
    if category_order:
        ordered_keys = [c.upper() for c in category_order if c.upper() in raw]
        remaining = sorted(k for k in raw if k not in ordered_keys)
        ordered_keys.extend(remaining)
    else:
        ordered_keys = sorted(raw.keys())

    result: Dict[str, Dict[str, Any]] = {}
    for cat in ordered_keys:
        data = raw[cat]
        pct = (data["score"] / data["max_score"] * 100) if data["max_score"] > 0 else 0
        result[cat] = {
            "score": round(data["score"], 6),
            "max_score": round(data["max_score"], 6),
            "pct": round(pct, 1),
            "task_count": int(data["task_count"]),
        }

    return result


def _log_category_summary(
    task_entries: List[Dict[str, Any]],
    tasks_by_id: Dict[str, Any],
    category_order: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Log a summary grouped by category, matching the PinchBench website format.

    Returns the computed category_scores dict so callers can embed it in
    results JSON.
    """
    category_scores = _compute_category_scores(task_entries, tasks_by_id, category_order)

    # Calculate overall totals
    total_earned = sum(c["score"] for c in category_scores.values())
    total_possible = sum(c["max_score"] for c in category_scores.values())
    overall_pct = (total_earned / total_possible * 100) if total_possible > 0 else 0

    logger.info("\n%s", "=" * 80)
    logger.info("🦀 PINCHBENCH SCORE SUMMARY")
    logger.info("%s", "=" * 80)
    logger.info("")
    logger.info("   Overall Score: %.1f%% (%.1f / %.1f)", overall_pct, total_earned, total_possible)
    logger.info("")
    logger.info("   %-20s %8s %12s", "CATEGORY", "SCORE", "TASKS")
    logger.info("   %s", "-" * 44)

    for category, data in category_scores.items():
        pct = data["pct"]
        task_count = data["task_count"]
        task_label = "task" if task_count == 1 else "tasks"

        # Color indicator based on score
        if pct >= 90:
            indicator = "🟢"
        elif pct >= 70:
            indicator = "🟡"
        else:
            indicator = "🔴"

        logger.info(
            "   %s %-17s %6.1f%% %6d %s",
            indicator,
            category,
            pct,
            task_count,
            task_label,
        )

    logger.info("   %s", "-" * 44)
    logger.info("%s", "=" * 80)

    return category_scores


def _snapshot_workspace_for_grading(execution_result: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot the workspace directory so a background grader reads stable files.

    When parallel grading is enabled, the main thread moves on to the next task
    and calls ``prepare_task_workspace`` which wipes and rebuilds the shared
    agent workspace.  If the background grader reads the live workspace it will
    see the *next* task's files instead of the current one's.

    This function copies the workspace tree into an isolated temp directory and
    returns a shallow copy of *execution_result* whose ``workspace`` key points
    to the snapshot.  The caller is responsible for cleaning up the temp
    directory once grading is complete.
    """
    workspace_path = execution_result.get("workspace", "")
    snapshot_result = dict(execution_result)  # shallow copy

    if workspace_path:
        src = Path(workspace_path)
        if src.exists() and src.is_dir():
            snapshot_dir = tempfile.mkdtemp(prefix="pinchbench_grade_snapshot_")
            shutil.copytree(src, Path(snapshot_dir) / "workspace", dirs_exist_ok=True)
            snapshot_result["workspace"] = str(Path(snapshot_dir) / "workspace")
            # Stash the root temp dir so we can clean it up later
            snapshot_result["_snapshot_tmpdir"] = snapshot_dir

    return snapshot_result


def main():
    """Main entry point for the benchmark script."""
    # Determine tasks directory
    script_dir = Path(__file__).parent
    skill_root = script_dir.parent  # Parent of scripts/ is the skill root
    tasks_dir = skill_root / "tasks"

    logger.info("🦞🦀🦐 PinchBench - OpenClaw Benchmarking")
    ascii_crab = _load_ascii_art(skill_root, "crab.txt")
    if ascii_crab:
        print("\n" + _colorize_gradient(ascii_crab) + "\n")
    else:
        print("\n" + "🦀 " * 30)
        print("🦀 " * 30 + "\n")
    logger.info("🦞🦀🦐 Starting PinchBench 🦐🦀🦞")
    time.sleep(5)

    if not tasks_dir.exists():
        logger.error(f"❌ Tasks directory not found: {tasks_dir}")
        sys.exit(1)

    args = _parse_args()
    if not args.model and not args.register and not args.upload:
        logger.error("Missing required argument: --model (unless using --register or --upload)")
        sys.exit(2)

    if args.register:
        try:
            from lib_upload import UploadError, register_token, save_token_config

            token, claim_url = register_token()
            config_path = save_token_config(token, claim_url)
            logger.info("Saved token to %s", config_path)
            if claim_url:
                logger.info("Claim URL: %s", claim_url)
            return
        except UploadError as exc:
            logger.error("Registration failed: %s", exc)
            sys.exit(1)

    if args.upload:
        results_path = Path(args.upload)
        if not results_path.exists():
            logger.error("Results file not found: %s", results_path)
            sys.exit(1)
        try:
            from lib_upload import UploadError, upload_results

            result = upload_results(results_path)
            if result.rank is not None:
                logger.info("Uploaded to leaderboard: rank #%s", result.rank)
            if result.leaderboard_url:
                logger.info("View at: %s", result.leaderboard_url)
            logger.info("Upload complete.")
            return
        except UploadError as exc:
            logger.error("Upload failed: %s", exc)
            sys.exit(1)

    # Initialize judge cache
    if not args.no_judge_cache:
        cache_dir = Path(args.output_dir) / ".judge_cache"
        set_judge_cache_dir(cache_dir)
        if args.clear_judge_cache:
            clear_judge_cache()
            logger.info("🗑️  Judge cache cleared")
    else:
        logger.info("📦 Judge caching disabled")
    
    logger.info("🔧 Initializing BenchmarkRunner...")
    runner = BenchmarkRunner(tasks_dir)

    logger.info("📂 Loading tasks from directory...")
    runner.load_tasks()

    model_slug = slugify_model(args.model)
    run_root = Path("/tmp/pinchbench")
    run_id = _next_run_id(run_root)
    skill_dir = skill_root
    agent_id = f"bench-{model_slug}"
    # Use a shared workspace for the agent - we'll copy fixtures per task
    agent_workspace = Path(f"/tmp/pinchbench/{run_id}/agent_workspace")

    # Validate model exists before wasting time on tasks
    if args.base_url:
        logger.info("Using custom endpoint: %s (skipping OpenRouter validation)", args.base_url)
    else:
        try:
            validate_openrouter_model(args.model)
        except ModelValidationError as exc:
            logger.error("❌ %s", exc)
            sys.exit(1)

    ensure_agent_exists(
        agent_id,
        args.model,
        agent_workspace,
        base_url=args.base_url,
        api_key=args.api_key,
    )
    cleanup_agent_sessions(agent_id)

    task_ids = _select_task_ids(runner.tasks, args.suite, runner.task_loader.category_map)
    
    # Handle --core flag: use core tasks from manifest
    if args.core:
        core_task_ids = runner.task_loader.core_tasks
        if not core_task_ids:
            logger.warning("⚠️  No core tasks defined in manifest.yaml, running all tasks")
        else:
            task_ids = core_task_ids
            logger.info(f"🎯 Core mode: running {len(core_task_ids)} representative tasks")
    
    results = []
    grades_by_task_id = {}
    sanity_task_id = "task_sanity"

    tasks_to_run = runner.tasks
    if task_ids is not None:
        tasks_map = {task.task_id: task for task in runner.tasks}
        tasks_to_run = [tasks_map[tid] for tid in task_ids if tid in tasks_map]
    tasks_by_id = {task.task_id: task for task in tasks_to_run}

    # Initialize Axiom logging (silently no-ops if AXIOM_API_TOKEN not set)
    axiom = init_axiom(
        run_id=run_id,
        model=args.model,
        benchmark_version=_get_benchmark_version(skill_root),
    )
    axiom.run_start(total_tasks=len(tasks_to_run), suite=args.suite)

    runs_per_task = max(1, args.runs)

    # Incremental result writer: builds partial result JSON from completed
    # tasks so external tools can poll progress while the benchmark runs.
    incremental_dir = Path(args.output_dir)
    incremental_dir.mkdir(parents=True, exist_ok=True)
    incremental_path = incremental_dir / f"{run_id}_{model_slug}.json"

    category_map = runner.task_loader.category_map
    category_order = runner.task_loader.categories

    def _build_task_entry(r: Dict[str, Any]) -> Dict[str, Any]:
        """Build a single task entry dict for results JSON."""
        tid = r["task_id"]
        entry: Dict[str, Any] = {
            "task_id": tid,
            "status": r["status"],
            "timed_out": r["timed_out"],
            "execution_time": r["execution_time"],
            "transcript_length": len(r["transcript"]),
            "usage": r.get("usage", {}),
            "workspace": r["workspace"],
            "grading": grades_by_task_id.get(tid, {}),
            "frontmatter": tasks_by_id[tid].frontmatter,
        }
        if category_map:
            entry["category"] = category_map.get(tid, "")
        return entry

    def _write_incremental_results():
        task_entries = [_build_task_entry(r) for r in results]
        efficiency = _compute_efficiency_summary(task_entries, grades_by_task_id)
        cat_scores = _compute_category_scores(task_entries, tasks_by_id, category_order)
        partial = {
            "model": args.model,
            "benchmark_version": _get_benchmark_version(skill_root),
            "run_id": run_id,
            "timestamp": time.time(),
            "suite": args.suite,
            "runs_per_task": runs_per_task,
            "tasks": task_entries,
            "category_scores": cat_scores,
            "efficiency": efficiency,
            "in_progress": True,
            "completed_tasks": len(grades_by_task_id),
            "total_tasks": len(tasks_to_run),
        }
        try:
            incremental_path.write_text(json.dumps(partial, indent=2), encoding="utf-8")
        except OSError:
            pass

    # Parallel judge execution: grade previous task while current task runs
    use_parallel_judge = not args.no_parallel_judge
    judge_executor: Optional[ThreadPoolExecutor] = None
    pending_grade_future: Optional[Future] = None
    pending_grade_task: Optional[Task] = None
    pending_grade_result: Optional[Dict[str, Any]] = None
    pending_grade_task_num: int = 0
    pending_grade_snapshot_dir: Optional[str] = None  # temp dir to clean up after grading

    if use_parallel_judge:
        judge_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="judge")
        logger.info("Parallel judge execution enabled")

    def _wait_for_pending_grade() -> None:
        """Wait for any pending background grade to complete and record it."""
        nonlocal pending_grade_future, pending_grade_task, pending_grade_result, pending_grade_task_num, pending_grade_snapshot_dir
        if pending_grade_future is None:
            return

        try:
            grade = pending_grade_future.result(timeout=DEFAULT_JUDGE_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.warning("Background grading failed for %s: %s", pending_grade_task.task_id, exc)
            grade = GradeResult(
                task_id=pending_grade_task.task_id,
                score=0.0,
                max_score=1.0,
                grading_type=pending_grade_task.grading_type,
                breakdown={},
                notes=f"Background grading failed: {exc}",
            )

        # Log the grade
        score_pct = grade.score / grade.max_score * 100 if grade.max_score > 0 else 0
        status_emoji = "✅" if grade.score >= grade.max_score else "⚠️" if grade.score > 0 else "❌"
        logger.info(
            "%s Task %s: %.1f/%.1f (%.0f%%) - %s [background]",
            status_emoji,
            pending_grade_task.task_id,
            grade.score,
            grade.max_score,
            score_pct,
            grade.grading_type,
        )
        if grade.notes:
            logger.info("   Notes: %s", grade.notes[:200])

        # Log to Axiom
        axiom.task_complete(
            task_id=pending_grade_task.task_id,
            task_num=pending_grade_task_num,
            total_tasks=len(tasks_to_run),
            score=grade.score,
            max_score=grade.max_score,
            grading_type=grade.grading_type,
            execution_time_sec=pending_grade_result.get("execution_time", 0.0),
            timed_out=pending_grade_result.get("timed_out", False),
        )

        # Record the grade
        task_scores = [grade.score]
        grades_by_task_id[pending_grade_task.task_id] = {
            "runs": [grade.to_dict()],
            "mean": statistics.mean(task_scores),
            "std": 0.0,
            "min": min(task_scores),
            "max": max(task_scores),
        }

        # Clean up workspace snapshot temp directory
        if pending_grade_snapshot_dir:
            shutil.rmtree(pending_grade_snapshot_dir, ignore_errors=True)
            pending_grade_snapshot_dir = None

        pending_grade_future = None
        pending_grade_task = None
        pending_grade_result = None

    for i, task in enumerate(tasks_to_run, 1):
        # Wait for previous task's background grade before starting new task
        # (we need to record its results before they get overwritten)
        _wait_for_pending_grade()

        task_grades = []
        task_results = []
        for run_index in range(runs_per_task):
            logger.info("\n%s", "=" * 80)
            logger.info(
                "📋 Task %s/%s (Run %s/%s)",
                i,
                len(tasks_to_run),
                run_index + 1,
                runs_per_task,
            )
            logger.info("%s", "=" * 80)
            execution_error = None
            try:
                result = execute_openclaw_task(
                    task=task,
                    agent_id=agent_id,
                    model_id=args.model,
                    run_id=f"{run_id}-{run_index + 1}",
                    timeout_multiplier=args.timeout_multiplier,
                    skill_dir=skill_dir,
                    output_dir=Path(args.output_dir) / f"{run_id}_transcripts",
                    verbose=args.verbose,
                )
            except Exception as exc:
                execution_error = str(exc)
                logger.warning("Task execution failed for %s, continuing: %s", task.task_id, exc)
                result = {
                    "agent_id": agent_id,
                    "task_id": task.task_id,
                    "status": "error",
                    "transcript": [],
                    "usage": {},
                    "workspace": "",
                    "exit_code": -1,
                    "timed_out": False,
                    "execution_time": 0.0,
                    "stdout": "",
                    "stderr": execution_error,
                }

            task_results.append(result)
            results.append(result)

            # Build grade kwargs for this run
            grade_kwargs = dict(
                task=task, execution_result=result, skill_dir=skill_dir, verbose=args.verbose
            )
            if args.judge:
                grade_kwargs["judge_model"] = args.judge
                grade_kwargs["judge_backend"] = "api"

            # Parallel grading: submit to background if enabled and single run
            # For multi-run tasks, grade synchronously to maintain order
            is_last_task = (i == len(tasks_to_run))
            can_parallelize = (
                use_parallel_judge
                and judge_executor is not None
                and runs_per_task == 1
                and not is_last_task
            )

            if can_parallelize:
                # Snapshot workspace so the background grader reads stable
                # files even after the main thread rebuilds the workspace for
                # the next task.
                snapshot_result = _snapshot_workspace_for_grading(result)
                grade_kwargs["execution_result"] = snapshot_result

                # Submit grading to background thread
                pending_grade_future = judge_executor.submit(grade_task, **grade_kwargs)
                pending_grade_task = task
                pending_grade_result = result
                pending_grade_task_num = i
                pending_grade_snapshot_dir = snapshot_result.get("_snapshot_tmpdir")
                logger.info("   Grading submitted to background thread (workspace snapshotted)")
                # Don't wait - continue to next task
                # Results will be recorded when we call _wait_for_pending_grade()
                continue
            else:
                # Synchronous grading
                try:
                    grade = grade_task(**grade_kwargs)
                except Exception as exc:
                    if execution_error:
                        note = f"Execution failed: {execution_error}; Grading failed: {exc}"
                    else:
                        note = f"Grading failed: {exc}"
                    logger.warning("Task grading failed for %s, continuing: %s", task.task_id, exc)
                    grade = GradeResult(
                        task_id=task.task_id,
                        score=0.0,
                        max_score=1.0,
                        grading_type=task.grading_type,
                        breakdown={},
                        notes=note,
                    )
                task_grades.append(grade)

                # Log score immediately after grading
                score_pct = grade.score / grade.max_score * 100 if grade.max_score > 0 else 0
                status_emoji = (
                    "✅" if grade.score >= grade.max_score else "⚠️" if grade.score > 0 else "❌"
                )
                logger.info(
                    "%s Task %s: %.1f/%.1f (%.0f%%) - %s",
                    status_emoji,
                    task.task_id,
                    grade.score,
                    grade.max_score,
                    score_pct,
                    grade.grading_type,
                )
                if grade.notes:
                    logger.info("   Notes: %s", grade.notes[:200])

                # Log to Axiom
                axiom.task_complete(
                    task_id=task.task_id,
                    task_num=i,
                    total_tasks=len(tasks_to_run),
                    score=grade.score,
                    max_score=grade.max_score,
                    grading_type=grade.grading_type,
                    execution_time_sec=result.get("execution_time", 0.0),
                    timed_out=result.get("timed_out", False),
                    error=execution_error,
                )

        # Skip grades_by_task_id update if grading was submitted to background
        # EXCEPT for sanity task - we need to wait for it to enforce fail-fast
        if pending_grade_future is not None and pending_grade_task == task:
            if task.task_id == sanity_task_id and not args.no_fail_fast:
                # Wait for sanity grade synchronously to check fail-fast
                _wait_for_pending_grade()
                # Now task_grades will be empty, but grades_by_task_id is populated
                # Check fail-fast condition
                if (
                    sanity_task_id in grades_by_task_id
                    and grades_by_task_id[sanity_task_id]["mean"] == 0.0
                ):
                    logger.error(
                        "🚨 FAIL FAST: Sanity check (%s) scored 0%%. Aborting benchmark run to avoid wasting resources.",
                        sanity_task_id,
                    )
                    axiom.sanity_failed(score=grades_by_task_id[sanity_task_id]["mean"])
                    if judge_executor is not None:
                        judge_executor.shutdown(wait=False)
                    sys.exit(3)
            continue

        task_scores = [grade.score for grade in task_grades]
        grades_by_task_id[task.task_id] = {
            "runs": [grade.to_dict() for grade in task_grades],
            "mean": statistics.mean(task_scores),
            "std": statistics.stdev(task_scores) if len(task_scores) > 1 else 0.0,
            "min": min(task_scores),
            "max": max(task_scores),
        }

        all_runs_missing_transcript = all(
            not run_result.get("transcript") for run_result in task_results
        )
        if (
            task.task_id == sanity_task_id
            and grades_by_task_id[task.task_id]["mean"] == 0.0
            and not args.no_fail_fast
            and not all_runs_missing_transcript
        ):
            logger.error(
                "🚨 FAIL FAST: Sanity check (%s) scored 0%%. Aborting benchmark run to avoid wasting resources.",
                sanity_task_id,
            )
            axiom.sanity_failed(score=grades_by_task_id[task.task_id]["mean"])
            sys.exit(3)
        if task.task_id == sanity_task_id and grades_by_task_id[task.task_id]["mean"] == 0.0:
            if all_runs_missing_transcript:
                logger.warning(
                    "⚠️ Sanity check scored 0%% but transcripts were missing for all runs; skipping fail-fast as likely infrastructure/logging issue."
                )

        # Incremental write: update result JSON after each task so partial
        # results are available while the benchmark is still running.
        _write_incremental_results()

    # Wait for any final pending background grade
    _wait_for_pending_grade()

    # Shutdown the judge executor if we used one
    if judge_executor is not None:
        judge_executor.shutdown(wait=True)
        logger.info("Parallel judge executor shut down")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{run_id}_{model_slug}.json"

    def _build_and_write_results():
        """Build aggregate result from completed tasks and write to output_path."""
        task_entries = [_build_task_entry(r) for r in results]
        efficiency = _compute_efficiency_summary(task_entries, grades_by_task_id)
        cat_scores = _compute_category_scores(task_entries, tasks_by_id, category_order)
        aggregate = {
            "model": args.model,
            "benchmark_version": _get_benchmark_version(skill_root),
            "run_id": run_id,
            "timestamp": time.time(),
            "suite": args.suite,
            "runs_per_task": runs_per_task,
            "tasks": task_entries,
            "category_scores": cat_scores,
            "efficiency": efficiency,
        }
        output_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
        return task_entries, efficiency

    task_entries, efficiency = _build_and_write_results()

    # Calculate and log final score summary
    total_score = sum(grades_by_task_id[tid]["mean"] for tid in grades_by_task_id)
    max_score = float(len(grades_by_task_id))  # Each task has max_score of 1.0
    score_pct = (total_score / max_score * 100) if max_score > 0 else 0
    logger.info("📊 Final score: %.2f/%.0f (%.1f%%)", total_score, max_score, score_pct)

    # Log judge cache stats
    if not args.no_judge_cache:
        cache_stats = get_judge_cache_stats()
        if cache_stats["hits"] > 0 or cache_stats["misses"] > 0:
            hit_rate = cache_stats["hits"] / (cache_stats["hits"] + cache_stats["misses"]) * 100
            logger.info(
                "📦 Judge cache: %d hits, %d misses (%.0f%% hit rate, %d entries)",
                cache_stats["hits"],
                cache_stats["misses"],
                hit_rate,
                cache_stats["entries"],
            )

    logger.info("Saved results to %s", output_path)
    _log_category_summary(task_entries, tasks_by_id, category_order)
    _log_efficiency_summary(efficiency, grades_by_task_id)
    # Run trend analysis if requested
    if args.trend:
        try:
            from lib_trend import RunTrendAnalyzer

            analyzer = RunTrendAnalyzer(
                results_dir=output_dir,
                window=args.trend_window,
                regression_threshold=args.trend_threshold,
            )
            analyzer.run(model=args.model)
        except Exception as exc:
            logger.warning("Trend analysis failed: %s", exc)

    submission_id = None
    leaderboard_url = None

    if args.no_upload:
        logger.info("Skipping upload (--no-upload)")
    else:
        try:
            from lib_upload import UploadError, upload_results

            result = upload_results(output_path, official_key=args.official_key)
            if result.submission_id:
                logger.info("Submission ID: %s", result.submission_id)
                submission_id = result.submission_id
            if result.rank is not None:
                logger.info("Uploaded to leaderboard: rank #%s", result.rank)
            if result.leaderboard_url:
                logger.info("View at: %s", result.leaderboard_url)
                leaderboard_url = result.leaderboard_url
        except UploadError as exc:
            logger.warning("Upload failed: %s", exc)
            axiom.upload_failed(error=str(exc))

    # Log run completion to Axiom
    total_time_sec = sum(r.get("execution_time", 0.0) for r in results)
    axiom.run_complete(
        overall_score_pct=score_pct,
        overall_earned=total_score,
        overall_possible=max_score,
        total_cost_usd=efficiency.get("total_cost_usd"),
        total_time_sec=total_time_sec,
        submission_id=submission_id,
        leaderboard_url=leaderboard_url,
    )


if __name__ == "__main__":
    main()
