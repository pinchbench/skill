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
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from lib_agent import (
    cleanup_agent_sessions,
    ensure_agent_exists,
    execute_openclaw_task,
    ModelValidationError,
    slugify_model,
    validate_openrouter_model,
    THINKING_LEVELS,
    validate_thinking_level,
)
from lib_grading import GradeResult, grade_task
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
        help='Tasks to run: "all", "automated-only", or comma-separated IDs',
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
        "--thinking",
        type=str,
        default=None,
        help="Comma-separated thinking levels to test (e.g., 'low,medium,high'). "
        f"Valid levels: {', '.join(THINKING_LEVELS)}. "
        "Note: 'xhigh' requires GPT-5.x models; 'adaptive' is for Anthropic Claude 4.6. "
        "If not specified, runs without explicit thinking level.",
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


def _select_task_ids(tasks: List[Task], suite: str) -> Optional[List[str]]:
    if suite == "all":
        return None
    if suite == "automated-only":
        return [task.task_id for task in tasks if task.grading_type == "automated"]
    return [task_id.strip() for task_id in suite.split(",") if task_id.strip()]


def _parse_thinking_levels(
    thinking_arg: Optional[str],
    model_id: Optional[str] = None,
) -> List[Optional[str]]:
    """
    Parse thinking levels from the argument.

    Args:
        thinking_arg: Comma-separated thinking levels or None
        model_id: Optional model ID to check level compatibility

    Returns:
        List of validated thinking levels (or [None] if no explicit level).

    Raises:
        ValueError: If --thinking was provided but no levels are valid for the model.
    """
    if thinking_arg is None:
        return [None]  # Run once without explicit thinking level

    levels: List[str] = []
    seen = set()
    for level in thinking_arg.split(","):
        validated = validate_thinking_level(level.strip(), model_id)
        if validated and validated not in seen:
            levels.append(validated)
            seen.add(validated)

    if not levels:
        raise ValueError(
            "No valid thinking levels remain after validation. "
            "Check your --thinking values for this model."
        )

    return levels


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


def _log_category_summary(
    task_entries: List[Dict[str, Any]],
    tasks_by_id: Dict[str, Any],
) -> None:
    """Log a summary grouped by category, matching the PinchBench website format."""
    # Group scores by category
    category_scores: Dict[str, Dict[str, float]] = {}

    for entry in task_entries:
        task_id = entry["task_id"]
        task = tasks_by_id.get(task_id)
        if not task:
            continue

        category = task.category.upper() if task.category else "UNCATEGORIZED"
        grading = entry.get("grading", {})
        mean_score = float(grading.get("mean", 0.0))
        max_score = 1.0  # Each task is scored 0-1

        if category not in category_scores:
            category_scores[category] = {"earned": 0.0, "possible": 0.0, "task_count": 0}

        category_scores[category]["earned"] += mean_score
        category_scores[category]["possible"] += max_score
        category_scores[category]["task_count"] += 1

    # Calculate overall totals
    total_earned = sum(c["earned"] for c in category_scores.values())
    total_possible = sum(c["possible"] for c in category_scores.values())
    overall_pct = (total_earned / total_possible * 100) if total_possible > 0 else 0

    logger.info("\n%s", "=" * 80)
    logger.info("🦀 PINCHBENCH SCORE SUMMARY")
    logger.info("%s", "=" * 80)
    logger.info("")
    logger.info("   Overall Score: %.1f%% (%.1f / %.1f)", overall_pct, total_earned, total_possible)
    logger.info("")
    logger.info("   %-20s %8s %12s", "CATEGORY", "SCORE", "TASKS")
    logger.info("   %s", "-" * 44)

    # Sort categories alphabetically for consistent output
    for category in sorted(category_scores.keys()):
        data = category_scores[category]
        pct = (data["earned"] / data["possible"] * 100) if data["possible"] > 0 else 0
        task_count = int(data["task_count"])
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

    task_ids = _select_task_ids(runner.tasks, args.suite)
    try:
        thinking_levels = _parse_thinking_levels(args.thinking, args.model)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(2)
    results = []
    grades_by_task_id: Dict[str, Dict[str, Any]] = {}
    grades_by_task_and_thinking: Dict[str, Dict[str, Any]] = {}
    sanity_task_id = "task_sanity"

    tasks_to_run = runner.tasks
    if task_ids is not None:
        tasks_to_run = [task for task in runner.tasks if task.task_id in task_ids]
    tasks_by_id = {task.task_id: task for task in tasks_to_run}

    runs_per_task = max(1, args.runs)
    total_runs = len(tasks_to_run) * runs_per_task * len(thinking_levels)
    run_counter = 0

    for thinking_level in thinking_levels:
        thinking_label = thinking_level or "default"
        logger.info("\n%s", "=" * 80)
        logger.info("🧠 Thinking Level: %s", thinking_label)
        logger.info("%s", "=" * 80)

        for i, task in enumerate(tasks_to_run, 1):
            task_key = f"{task.task_id}:{thinking_label}" if thinking_level else task.task_id
            task_grades = []
            task_results = []

            for run_index in range(runs_per_task):
                run_counter += 1
                logger.info("\n%s", "-" * 80)
                logger.info(
                    "📋 Task %s/%s (Run %s/%s) [%s] — Overall progress: %s/%s",
                    i,
                    len(tasks_to_run),
                    run_index + 1,
                    runs_per_task,
                    thinking_label,
                    run_counter,
                    total_runs,
                )
                logger.info("%s", "-" * 80)
                execution_error = None
                try:
                    result = execute_openclaw_task(
                        task=task,
                        agent_id=agent_id,
                        model_id=args.model,
                        run_id=f"{run_id}-{run_index + 1}",
                        timeout_multiplier=args.timeout_multiplier,
                        skill_dir=skill_dir,
                        thinking_level=thinking_level,
                    )
                except Exception as exc:
                    execution_error = str(exc)
                    logger.warning(
                        "Task execution failed for %s, continuing: %s", task.task_id, exc
                    )
                    result = {
                        "agent_id": agent_id,
                        "task_id": task.task_id,
                        "thinking_level": thinking_level,
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
                try:
                    grade = grade_task(task=task, execution_result=result, skill_dir=skill_dir)
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
                result["thinking_level"] = thinking_level
                results.append(result)

            task_scores = [grade.score for grade in task_grades]
            grades_by_task_and_thinking[task_key] = {
                "task_id": task.task_id,
                "thinking_level": thinking_level,
                "runs": [grade.to_dict() for grade in task_grades],
                "mean": statistics.mean(task_scores),
                "std": statistics.stdev(task_scores) if len(task_scores) > 1 else 0.0,
                "min": min(task_scores),
                "max": max(task_scores),
            }

    # Compute per-thinking-level aggregates
    thinking_aggregates: Dict[str, Dict[str, Any]] = {}
    for thinking_level in thinking_levels:
        thinking_label = thinking_level or "default"
        level_keys = [
            k
            for k, v in grades_by_task_and_thinking.items()
            if v.get("thinking_level") == thinking_level
        ]
        if not level_keys:
            continue
        scores = [grades_by_task_and_thinking[k]["mean"] for k in level_keys]
        thinking_aggregates[thinking_label] = {
            "thinking_level": thinking_label,
            "task_count": len(scores),
            "mean_score": statistics.mean(scores) if scores else 0.0,
            "std_score": statistics.stdev(scores) if len(scores) > 1 else 0.0,
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0,
        }

    incremental_dir = Path(args.output_dir)
    incremental_dir.mkdir(parents=True, exist_ok=True)
    incremental_path = incremental_dir / f"{run_id}_{model_slug}.json"

    def _write_incremental_results():
        task_entries = [
            {
                "task_id": r["task_id"],
                "status": r["status"],
                "timed_out": r["timed_out"],
                "execution_time": r["execution_time"],
                "transcript_length": len(r["transcript"]),
                "usage": r.get("usage", {}),
                "workspace": r["workspace"],
                "grading": grades_by_task_and_thinking.get(
                    f"{r['task_id']}:{r.get('thinking_level') or 'default'}",
                    {},
                ),
                "frontmatter": tasks_by_id[r["task_id"]].frontmatter,
            }
            for r in results
        ]
        efficiency = _compute_efficiency_summary(task_entries, grades_by_task_and_thinking)
        partial = {
            "model": args.model,
            "benchmark_version": _get_benchmark_version(skill_root),
            "run_id": run_id,
            "timestamp": time.time(),
            "suite": args.suite,
            "runs_per_task": runs_per_task,
            "thinking_levels": [tl or "default" for tl in thinking_levels],
            "thinking_aggregates": thinking_aggregates,
            "tasks": task_entries,
            "efficiency": efficiency,
            "in_progress": True,
            "completed_tasks": len(grades_by_task_and_thinking),
            "total_tasks": len(tasks_to_run) * len(thinking_levels),
        }
        try:
            incremental_path.write_text(json.dumps(partial, indent=2), encoding="utf-8")
        except OSError:
            pass

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{run_id}_{model_slug}.json"

    _write_incremental_results()

    task_entries = [
        {
            "task_id": result["task_id"],
            "status": result["status"],
            "timed_out": result["timed_out"],
            "execution_time": result["execution_time"],
            "transcript_length": len(result["transcript"]),
            "usage": result.get("usage", {}),
            "workspace": result["workspace"],
            "grading": grades_by_task_and_thinking.get(
                f"{result['task_id']}:{result.get('thinking_level') or 'default'}",
                {},
            ),
            "frontmatter": tasks_by_id[result["task_id"]].frontmatter,
        }
        for result in results
    ]
    efficiency = _compute_efficiency_summary(task_entries, grades_by_task_and_thinking)
    aggregate = {
        "model": args.model,
        "benchmark_version": _get_benchmark_version(skill_root),
        "run_id": run_id,
        "timestamp": time.time(),
        "suite": args.suite,
        "runs_per_task": runs_per_task,
        "thinking_levels": [tl or "default" for tl in thinking_levels],
        "thinking_aggregates": thinking_aggregates,
        "tasks": task_entries,
        "efficiency": efficiency,
    }
    output_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    # Calculate and log final score summary
    total_score = sum(v["mean"] for v in grades_by_task_and_thinking.values())
    max_score = float(len(grades_by_task_and_thinking))
    score_pct = (total_score / max_score * 100) if max_score > 0 else 0
    logger.info("📊 Final score: %.2f/%.0f (%.1f%%)", total_score, max_score, score_pct)

    logger.info("Saved results to %s", output_path)
    _log_category_summary(task_entries, tasks_by_id)
    _log_efficiency_summary(efficiency, grades_by_task_and_thinking)
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

    if args.no_upload:
        logger.info("Skipping upload (--no-upload)")
    else:
        try:
            from lib_upload import UploadError, upload_results

            result = upload_results(output_path, official_key=args.official_key)
            if result.submission_id:
                logger.info("Submission ID: %s", result.submission_id)
            if result.rank is not None:
                logger.info("Uploaded to leaderboard: rank #%s", result.rank)
            if result.leaderboard_url:
                logger.info("View at: %s", result.leaderboard_url)
        except UploadError as exc:
            logger.warning("Upload failed: %s", exc)


if __name__ == "__main__":
    main()
