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
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib_agent import (
    cleanup_agent_sessions,
    ensure_agent_exists,
    execute_openclaw_task,
    ModelValidationError,
    slugify_model,
    validate_openrouter_model,
)
from lib_grading import DEFAULT_JUDGE_TIMEOUT_SECONDS, GradeResult, grade_task, grade_tasks_batch
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
        # Initialize judge executor for parallel grading
    judge_executor: Optional[ThreadPoolExecutor] = None
    if not args.no_parallel_judge:
        judge_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="judge")
        logger.info("🚀 Parallel judge execution enabled")
    else:
        logger.info("⏸️  Parallel judge execution disabled (--no-parallel-judge)")

    # Track pending grade from previous run
    pending_grade: Optional[Tuple[str, List, List, int, Future]] = None

    try:
        for i, task in enumerate(tasks_to_run, 1):
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
                
                # Process pending grade from previous run
                if pending_grade:
                    prev_task_id, prev_grades, prev_results, prev_run_idx, future = pending_grade
                    try:
                        grade = future.result(timeout=DEFAULT_JUDGE_TIMEOUT_SECONDS)
                        prev_grades.append(grade)
                        
                        score_pct = grade.score / grade.max_score * 100 if grade.max_score > 0 else 0
                        status_emoji = (
                            "✅" if grade.score >= grade.max_score else "⚠️" if grade.score > 0 else "❌"
                        )
                        logger.info(
                            "%s Task %s (run %d, background): %.1f/%.1f (%.0f%%) - %s",
                            status_emoji,
                            prev_task_id,
                            prev_run_idx + 1,
                            grade.score,
                            grade.max_score,
                            score_pct,
                            grade.grading_type,
                        )
                        if grade.notes:
                            logger.info("   Notes: %s", grade.notes[:200])
                        
                        # If last run of previous task, compute aggregates
                        if len(prev_grades) == runs_per_task:
                            task_scores = [g.score for g in prev_grades]
                            grades_by_task_id[prev_task_id] = {
                                "runs": [g.to_dict() for g in prev_grades],
                                "mean": statistics.mean(task_scores),
                                "std": statistics.stdev(task_scores) if len(task_scores) > 1 else 0.0,
                                "min": min(task_scores),
                                "max": max(task_scores),
                            }

                            all_runs_missing_transcript = all(
                                not run_result.get("transcript") for run_result in prev_results
                            )
                            if (
                                prev_task_id == sanity_task_id
                                and grades_by_task_id[prev_task_id]["mean"] == 0.0
                                and not args.no_fail_fast
                                and not all_runs_missing_transcript
                            ):
                                logger.error(
                                    "🚨 FAIL FAST: Sanity check (%s) scored 0%%. Aborting benchmark run.",
                                    sanity_task_id,
                                )
                                sys.exit(3)
                            if prev_task_id == sanity_task_id and grades_by_task_id[prev_task_id]["mean"] == 0.0:
                                if all_runs_missing_transcript:
                                    logger.warning(
                                        "⚠️ Sanity check scored 0%% but transcripts missing; skipping fail-fast."
                                    )

                            _write_incremental_results()
                            
                    except Exception as exc:
                        logger.warning("Background grade failed for %s (run %d): %s", 
                                     prev_task_id, prev_run_idx + 1, exc)
                        grade = GradeResult(
                            task_id=prev_task_id,
                            score=0.0,
                            max_score=1.0,
                            grading_type="error",
                            breakdown={},
                            notes=f"Background grading failed: {exc}",
                        )
                        prev_grades.append(grade)
                    pending_grade = None
                
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
                
                # Decide sync vs async grading
                is_last_run = (run_index == runs_per_task - 1) and (i == len(tasks_to_run))
                
                if args.no_parallel_judge or is_last_run:
                    # Synchronous grading
                    try:
                        grade_kwargs = dict(
                            task=task, execution_result=result, skill_dir=skill_dir, verbose=args.verbose
                        )
                        if args.judge:
                            grade_kwargs["judge_model"] = args.judge
                            grade_kwargs["judge_backend"] = "api"
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

                    # Log score immediately
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
                else:
                    # Async grading - submit to background
                    logger.info("⏭️  Submitting grading to background thread...")
                    grade_kwargs = dict(
                        task=task, execution_result=result, skill_dir=skill_dir, verbose=args.verbose
                    )
                    if args.judge:
                        grade_kwargs["judge_model"] = args.judge
                        grade_kwargs["judge_backend"] = "api"
                    
                    future = judge_executor.submit(grade_task, **grade_kwargs)
                    pending_grade = (task.task_id, task_grades, task_results, run_index, future)

            # If synchronous mode, compute aggregates now
            if args.no_parallel_judge:
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
                        "🚨 FAIL FAST: Sanity check (%s) scored 0%%. Aborting benchmark run.",
                        sanity_task_id,
                    )
                    sys.exit(3)
                if task.task_id == sanity_task_id and grades_by_task_id[task.task_id]["mean"] == 0.0:
                    if all_runs_missing_transcript:
                        logger.warning(
                            "⚠️ Sanity check scored 0%% but transcripts missing; skipping fail-fast."
                        )

                _write_incremental_results()
        
        # Process any remaining pending grade
        if pending_grade:
            prev_task_id, prev_grades, prev_results, prev_run_idx, future = pending_grade
            try:
                grade = future.result(timeout=DEFAULT_JUDGE_TIMEOUT_SECONDS)
                prev_grades.append(grade)
                
                score_pct = grade.score / grade.max_score * 100 if grade.max_score > 0 else 0
                status_emoji = (
                    "✅" if grade.score >= grade.max_score else "⚠️" if grade.score > 0 else "❌"
                )
                logger.info(
                    "%s Task %s (run %d, final): %.1f/%.1f (%.0f%%) - %s",
                    status_emoji,
                    prev_task_id,
                    prev_run_idx + 1,
                    grade.score,
                    grade.max_score,
                    score_pct,
                    grade.grading_type,
                )
                if grade.notes:
                    logger.info("   Notes: %s", grade.notes[:200])
                
                task_scores = [g.score for g in prev_grades]
                grades_by_task_id[prev_task_id] = {
                    "runs": [g.to_dict() for g in prev_grades],
                    "mean": statistics.mean(task_scores),
                    "std": statistics.stdev(task_scores) if len(task_scores) > 1 else 0.0,
                    "min": min(task_scores),
                    "max": max(task_scores),
                }
                _write_incremental_results()
                    
            except Exception as exc:
                logger.warning("Final background grade failed for %s: %s", prev_task_id, exc)
    finally:
        # Cleanup executor
        if judge_executor:
            logger.info("🧹 Shutting down judge executor...")
            judge_executor.shutdown(wait=True)

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
