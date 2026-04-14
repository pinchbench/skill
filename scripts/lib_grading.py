"""
PinchBench grading engine.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib_agent import call_judge_api, ensure_agent_exists, run_openclaw_prompt, slugify_model
from lib_tasks import Task


logger = logging.getLogger(__name__)


DEFAULT_JUDGE_MODEL = "openrouter/anthropic/claude-opus-4.5"
DEFAULT_JUDGE_AGENT_PREFIX = "bench-judge"
DEFAULT_JUDGE_TIMEOUT_SECONDS = 300


@dataclass
class GradeResult:
    task_id: str
    score: float
    max_score: float
    grading_type: str
    breakdown: Dict[str, float]
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "score": self.score,
            "max_score": self.max_score,
            "grading_type": self.grading_type,
            "breakdown": self.breakdown,
            "notes": self.notes,
        }


def grade_task(
    *,
    task: Task,
    execution_result: Dict[str, Any],
    skill_dir: Path,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    judge_agent_prefix: str = DEFAULT_JUDGE_AGENT_PREFIX,
    judge_timeout_seconds: float = DEFAULT_JUDGE_TIMEOUT_SECONDS,
    judge_backend: str = "openclaw",
    verbose: bool = False,
) -> GradeResult:
    grading_type = task.grading_type
    if verbose:
        logger.info("   [VERBOSE] Grading task %s with type: %s", task.task_id, grading_type)
        logger.info("   [VERBOSE] Execution status: %s", execution_result.get("status", "unknown"))

    if grading_type == "automated":
        result = _grade_automated(task, execution_result, skill_dir=skill_dir, verbose=verbose)
        if verbose:
            logger.info("   [VERBOSE] Automated grade breakdown: %s", result.breakdown)
        return result
    if grading_type == "llm_judge":
        result = _grade_llm_judge(
            task=task,
            execution_result=execution_result,
            judge_model=judge_model,
            judge_agent_prefix=judge_agent_prefix,
            judge_timeout_seconds=judge_timeout_seconds,
            judge_backend=judge_backend,
            skill_dir=skill_dir,
            verbose=verbose,
        )
        if verbose:
            logger.info("   [VERBOSE] LLM judge breakdown: %s", result.breakdown)
        return result
    if grading_type == "hybrid":
        auto_result = _grade_automated(task, execution_result, skill_dir=skill_dir, verbose=verbose)
        llm_result = _grade_llm_judge(
            task=task,
            execution_result=execution_result,
            judge_model=judge_model,
            judge_agent_prefix=judge_agent_prefix,
            judge_timeout_seconds=judge_timeout_seconds,
            judge_backend=judge_backend,
            skill_dir=skill_dir,
            verbose=verbose,
        )
        return _combine_grades(task, auto_result, llm_result)
    raise ValueError(f"Unknown grading type: {grading_type}")


def _grade_automated(
    task: Task,
    execution_result: Dict[str, Any],
    skill_dir: Optional[Path] = None,
    verbose: bool = False,
) -> GradeResult:
    grading_code = _extract_grading_code(task)
    if not grading_code:
        return GradeResult(
            task_id=task.task_id,
            score=0.0,
            max_score=1.0,
            grading_type="automated",
            breakdown={},
            notes="No automated grading code found",
        )

    namespace = _build_automated_namespace(skill_dir)
    exec(grading_code, namespace)
    grade_func = namespace.get("grade")
    if not callable(grade_func):
        return GradeResult(
            task_id=task.task_id,
            score=0.0,
            max_score=1.0,
            grading_type="automated",
            breakdown={},
            notes="Automated grading function missing",
        )

    scores = grade_func(
        execution_result.get("transcript", []),
        execution_result.get("workspace", ""),
    )
    if not isinstance(scores, dict):
        scores = {}

    if verbose:
        logger.info("   [VERBOSE] Automated grading scores: %s", scores)

    total = _average_scores(scores)
    return GradeResult(
        task_id=task.task_id,
        score=total,
        max_score=1.0,
        grading_type="automated",
        breakdown=_normalize_score_dict(scores),
        notes="",
    )


_PRIVATE_IMAGE_KEY_FILENAME = "image_classification_answer_key.json"
_PRIVATE_IMAGE_KEY_RUNTIME_PATH = (
    Path("/tmp/pinchbench/judge/private") / _PRIVATE_IMAGE_KEY_FILENAME
)


def _build_automated_namespace(skill_dir: Optional[Path]) -> Dict[str, Any]:
    namespace: Dict[str, Any] = {}
    private_key_path = _stage_private_image_key(skill_dir)
    if private_key_path:
        namespace["_PINCHBENCH_PRIVATE_IMAGE_KEY_PATH"] = private_key_path
    return namespace


def _stage_private_image_key(skill_dir: Optional[Path]) -> str:
    if skill_dir is None:
        return ""
    source_key_path = skill_dir / "assets" / _PRIVATE_IMAGE_KEY_FILENAME
    if not source_key_path.exists():
        return ""

    try:
        _PRIVATE_IMAGE_KEY_RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PRIVATE_IMAGE_KEY_RUNTIME_PATH.write_bytes(source_key_path.read_bytes())
        os.chmod(_PRIVATE_IMAGE_KEY_RUNTIME_PATH, 0o600)
        return str(_PRIVATE_IMAGE_KEY_RUNTIME_PATH)
    except OSError as exc:
        logger.warning("Failed to stage private image answer key: %s", exc)
        return ""


def _grade_llm_judge(
    *,
    task: Task,
    execution_result: Dict[str, Any],
    judge_model: str,
    judge_agent_prefix: str,
    judge_timeout_seconds: float,
    judge_backend: str = "openclaw",
    skill_dir: Optional[Path] = None,
    verbose: bool = False,
) -> GradeResult:
    transcript = execution_result.get("transcript", [])
    execution_status = execution_result.get("status", "unknown")

    if not transcript and execution_status != "success":
        if verbose:
            logger.info(
                "   [VERBOSE] Skipping LLM judge: status=%s, transcript empty",
                execution_status,
            )
        return GradeResult(
            task_id=task.task_id,
            score=0.0,
            max_score=1.0,
            grading_type="llm_judge",
            breakdown={},
            notes=f"Skipped: task execution failed ({execution_status}), no transcript to evaluate",
        )

    transcript_summary = _summarize_transcript(transcript)
    if verbose:
        logger.info(
            "   [VERBOSE] Transcript summary for judge (first 1000 chars):\n%s",
            transcript_summary[:1000],
        )
    workspace_content = _read_workspace_files(execution_result.get("workspace", ""))
    if verbose and workspace_content:
        logger.info(
            "   [VERBOSE] Workspace files passed to judge (first 500 chars):\n%s",
            workspace_content[:500],
        )
    rubric = task.llm_judge_rubric or _format_grading_criteria(task)
    prompt = _build_judge_prompt(task, transcript_summary, rubric, workspace_content)

    max_judge_attempts = 2
    raw_parsed: Dict[str, Any] = {}
    for attempt in range(max_judge_attempts):
        if judge_backend == "api":
            # Direct API call — bypasses OpenClaw personality injection
            judge_result = call_judge_api(
                prompt=prompt,
                model=judge_model,
                timeout_seconds=judge_timeout_seconds,
            )

            if verbose:
                logger.info("   [VERBOSE] Judge execution status: %s", judge_result.get("status"))
                if judge_result.get("error"):
                    logger.info("   [VERBOSE] Judge error: %s", judge_result["error"])

            if judge_result.get("status") != "success":
                logger.warning(
                    "Judge API call failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_judge_attempts,
                    judge_result.get("error", judge_result.get("status")),
                )
                if attempt < max_judge_attempts - 1:
                    time.sleep(2**attempt)
                    continue

            raw_parsed = _parse_judge_text(judge_result.get("text", ""))
        else:
            # Default: OpenClaw agent session
            judge_skill_dir = skill_dir if skill_dir is not None else Path.cwd()
            agent_id = _ensure_judge_agent(judge_agent_prefix, judge_model, judge_skill_dir)
            judge_workspace = Path(f"/tmp/pinchbench/judge/{task.task_id}")
            judge_result = run_openclaw_prompt(
                agent_id=agent_id,
                prompt=prompt,
                workspace=judge_workspace,
                timeout_seconds=judge_timeout_seconds,
            )

            if verbose:
                logger.info("   [VERBOSE] Judge execution status: %s", judge_result.get("status"))
                logger.info("   [VERBOSE] Judge exit code: %s", judge_result.get("exit_code"))
                logger.info("   [VERBOSE] Judge stderr: %s", judge_result.get("stderr", "")[:500])

            if judge_result.get("status") != "success":
                logger.warning(
                    "Judge execution failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_judge_attempts,
                    judge_result.get("status"),
                )
                if attempt < max_judge_attempts - 1:
                    time.sleep(2**attempt)
                    continue

            raw_parsed = _parse_judge_response(judge_result.get("transcript", []))

        break  # Parsed response; exit loop after success or after the final failed attempt

    if verbose:
        logger.info("   [VERBOSE] Judge raw response parsed: %s", raw_parsed)

    # Normalize the response to handle various formats (criteria_scores, score, justification, etc.)
    parsed = _normalize_judge_response(raw_parsed)
    if verbose:
        logger.info("   [VERBOSE] Normalized judge response: %s", parsed)

    breakdown = parsed.get("scores", {})
    total = parsed.get("total")
    notes = parsed.get("notes", "")

    if not raw_parsed:
        notes = "LLM judge failed: no parseable response after all attempts"
        logger.warning("LLM judge for %s produced no parseable output", task.task_id)
    elif total is None:
        notes = "LLM judge failed: response parsed but no score extracted"
        logger.warning(
            "LLM judge for %s: parsed response but no total score found: %s",
            task.task_id,
            raw_parsed,
        )
    return GradeResult(
        task_id=task.task_id,
        score=float(total) if total is not None else 0.0,
        max_score=1.0,
        grading_type="llm_judge",
        breakdown=_normalize_score_dict(breakdown),
        notes=str(notes) if notes is not None else "",
    )


def _combine_grades(task: Task, auto_result: GradeResult, llm_result: GradeResult) -> GradeResult:
    weights = task.grading_weights or {"automated": 0.5, "llm_judge": 0.5}
    auto_weight = float(weights.get("automated", 0.5))
    llm_weight = float(weights.get("llm_judge", 0.5))
    total_weight = auto_weight + llm_weight
    if total_weight <= 0:
        auto_weight = llm_weight = 0.5
        total_weight = 1.0
    combined_score = (
        auto_result.score * auto_weight + llm_result.score * llm_weight
    ) / total_weight
    breakdown = {
        **{f"automated.{k}": v for k, v in auto_result.breakdown.items()},
        **{f"llm_judge.{k}": v for k, v in llm_result.breakdown.items()},
    }
    notes = " | ".join(filter(None, [auto_result.notes, llm_result.notes]))
    return GradeResult(
        task_id=task.task_id,
        score=combined_score,
        max_score=1.0,
        grading_type="hybrid",
        breakdown=breakdown,
        notes=notes,
    )


def _extract_grading_code(task: Task) -> str:
    if not task.automated_checks:
        return ""
    match = re.search(r"```python\s*(.*?)\s*```", task.automated_checks, re.DOTALL)
    if not match:
        return ""
    return match.group(1)


def _average_scores(scores: Dict[str, Any]) -> float:
    values = [float(v) for v in scores.values() if isinstance(v, (int, float))]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _normalize_score_dict(scores: Dict[str, Any]) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    for key, value in scores.items():
        try:
            normalized[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return normalized


def _format_grading_criteria(task: Task) -> str:
    if not task.grading_criteria:
        return ""
    return "\n".join(f"- {criterion}" for criterion in task.grading_criteria)


def _summarize_transcript(transcript: List[Dict[str, Any]]) -> str:
    summary_parts: List[str] = []
    for event in transcript:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})
        role = msg.get("role")
        if role == "assistant":
            for item in msg.get("content", []):
                if item.get("type") == "toolCall":
                    args = item.get("arguments", {})
                    truncated_args: Dict[str, Any] = {}
                    for k, v in args.items():
                        if isinstance(v, str) and len(v) > 200:
                            truncated_args[k] = v[:200] + "...[truncated]"
                        else:
                            truncated_args[k] = v
                    summary_parts.append(f"Tool: {item.get('name')}({json.dumps(truncated_args)})")
                elif item.get("type") == "text":
                    text = item.get("text", "").strip()
                    if text:
                        summary_parts.append(f"Assistant: {text[:2000]}")
        elif role == "toolResult":
            content = msg.get("content", [])
            if content:
                result_preview = str(content[0])[:200]
                summary_parts.append(f"Result: {result_preview}")
        elif role == "user":
            content = msg.get("content", [])
            if content:
                summary_parts.append(f"User: {content[0]}")
    return "\n".join(summary_parts)


def _read_workspace_files(workspace_path: str) -> str:
    """Read user-created text files from workspace to provide grading context."""
    if not workspace_path:
        return ""
    workspace = Path(workspace_path)
    if not workspace.exists():
        return ""
    skip_names = {
        "BOOTSTRAP.md",
        "SOUL.md",
        "USER.md",
        "IDENTITY.md",
        "HEARTBEAT.md",
        "TOOLS.md",
        "AGENTS.md",
    }
    skip_dirs = {".git", ".openclaw", "__pycache__", "node_modules", "skills"}
    file_contents: List[str] = []
    for f in sorted(workspace.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(workspace)
        parts = rel.parts
        if any(part.startswith(".") or part in skip_dirs for part in parts):
            continue
        if f.name in skip_names:
            continue
        try:
            content = f.read_text(encoding="utf-8")
            file_contents.append(f"### File: {rel}\n{content[:3000]}")
        except (OSError, UnicodeDecodeError):
            pass
    return "\n\n".join(file_contents)


def _build_judge_prompt(
    task: Task, transcript_summary: str, rubric: str, workspace_content: str = ""
) -> str:
    workspace_section = ""
    if workspace_content.strip():
        workspace_section = f"## Workspace Files Created by Agent\n{workspace_content}\n\n"
    return (
        "You are a grading function. Your ONLY job is to output a single JSON object.\n\n"
        "CRITICAL RULES:\n"
        "- Do NOT use any tools (no Read, Write, exec, or any other tool calls)\n"
        "- Do NOT create files or run commands\n"
        "- Do NOT write any prose, explanation, or commentary outside the JSON\n"
        "- Respond with ONLY a JSON object — nothing else\n\n"
        "Be a strict evaluator. Reserve 1.0 for genuinely excellent performance. "
        "An average acceptable completion should score around 0.6-0.7. "
        "Deduct points for unnecessary steps, verbose output, and inefficient tool usage.\n\n"
        "## Task\n"
        f"{task.prompt}\n\n"
        "## Expected Behavior\n"
        f"{task.expected_behavior}\n\n"
        "## Agent Transcript (summarized)\n"
        f"{transcript_summary}\n\n"
        f"{workspace_section}"
        "## Grading Rubric\n"
        f"{rubric}\n\n"
        "Score each criterion from 0.0 to 1.0.\n"
        'The "total" field must also be between 0.0 and 1.0, and it must be the arithmetic mean of the criterion scores, not their sum.\n\n'
        "Respond with ONLY this JSON structure (no markdown, no code fences, no extra text):\n"
        '{"scores": {"criterion_name": 0.0}, "total": 0.0, "notes": "brief justification"}'
    )


def _ensure_judge_agent(judge_agent_prefix: str, judge_model: str, skill_dir: Path) -> str:
    model_slug = slugify_model(judge_model)
    agent_id = f"{judge_agent_prefix}-{model_slug}"
    workspace = Path("/tmp/pinchbench/judge/workspace")
    ensure_agent_exists(agent_id, judge_model, workspace)
    return agent_id


def _parse_judge_response(transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
    content_chunks: List[str] = []
    for event in transcript:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})
        if msg.get("role") != "assistant":
            continue
        for item in msg.get("content", []):
            if item.get("type") == "text":
                content_chunks.append(item.get("text", ""))
    raw_text = "\n".join(content_chunks).strip()
    logger.info("   [VERBOSE] Judge raw response text (first 2000 chars):\n%s", raw_text[:2000])
    if not raw_text:
        return {}

    # First, try to extract JSON from code blocks (```json ... ```)
    code_block_match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
    if code_block_match:
        try:
            parsed = json.loads(code_block_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Find all potential JSON objects by looking for balanced braces
    # We'll extract chunks that start with { and try to parse them
    json_candidates: List[str] = []
    brace_depth = 0
    current_json = []
    for char in raw_text:
        if char == "{":
            if brace_depth == 0:
                current_json = []
            brace_depth += 1

        if brace_depth > 0:
            current_json.append(char)

        if char == "}":
            brace_depth -= 1
            if brace_depth == 0 and current_json:
                json_candidates.append("".join(current_json))

    # Try parsing from the last JSON object backwards (most recent response)
    for candidate in reversed(json_candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "scores" in parsed:
                # Prefer JSON that has the expected structure
                return parsed
        except json.JSONDecodeError:
            continue

    # Try any valid JSON dict
    for candidate in reversed(json_candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # Fallback: try to extract numeric scores from prose responses.
    # Models sometimes return "Total: 0.72" or "Overall score: 0.65" instead of JSON.
    score_pattern = re.search(
        r"(?:total|overall|final)\s*(?:score)?[:\s]*(0\.\d+|1\.0+)",
        raw_text,
        re.IGNORECASE,
    )
    if score_pattern:
        try:
            total = float(score_pattern.group(1))
            if 0.0 <= total <= 1.0:
                logger.warning("Fell back to regex score extraction from prose (total=%.2f)", total)
                return {
                    "scores": {},
                    "total": total,
                    "notes": "Score extracted from prose (JSON parse failed)",
                }
        except ValueError:
            pass

    logger.warning("Failed to parse judge JSON response")
    return {}


def _parse_judge_text(raw_text: str) -> Dict[str, Any]:
    """Parse judge response from raw text (direct API call, no OpenClaw transcript)."""
    raw_text = raw_text.strip()
    if not raw_text:
        return {}

    # Try direct JSON parse first (ideal case with system prompt enforcement)
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting from code blocks
    code_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
    if code_block_match:
        try:
            parsed = json.loads(code_block_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Find balanced-brace JSON objects
    json_candidates: List[str] = []
    brace_depth = 0
    current_json: List[str] = []
    for char in raw_text:
        if char == "{":
            if brace_depth == 0:
                current_json = []
            brace_depth += 1
        if brace_depth > 0:
            current_json.append(char)
        if char == "}":
            brace_depth -= 1
            if brace_depth == 0 and current_json:
                json_candidates.append("".join(current_json))

    for candidate in reversed(json_candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "scores" in parsed:
                return parsed
        except json.JSONDecodeError:
            continue
    for candidate in reversed(json_candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # Fallback: regex for total score
    score_pattern = re.search(
        r"(?:total|overall|final)\s*(?:score)?[:\s]*(0\.\d+|1\.0+)",
        raw_text,
        re.IGNORECASE,
    )
    if score_pattern:
        try:
            total = float(score_pattern.group(1))
            if 0.0 <= total <= 1.0:
                logger.warning("Fell back to regex score extraction (total=%.2f)", total)
                return {"scores": {}, "total": total, "notes": "Score extracted from prose"}
        except ValueError:
            pass

    logger.warning(
        "Failed to parse judge text response. Raw text (first 500 chars): %s", raw_text[:500]
    )
    return {}


def _normalize_judge_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize judge response to expected format with 'scores', 'total', and 'notes'.

    Handles various response formats:
    - {"scores": {...}, "total": 0.9, "notes": "..."}  (expected)
    - {"criteria_scores": {...}, ...}  (Claude sometimes uses this)
    - {"score": 0.9, "justification": "..."}  (simplified format)
    """
    result: Dict[str, Any] = {"scores": {}, "total": None, "notes": ""}

    # Extract scores from various keys
    if "scores" in parsed:
        scores_data = parsed["scores"]
        if isinstance(scores_data, dict):
            # Handle nested structure: {"criterion": {"score": 0.9, "weight": 0.3}}
            for key, value in scores_data.items():
                if isinstance(value, dict) and "score" in value:
                    result["scores"][key] = (
                        float(value["score"])
                        if isinstance(value["score"], (int, float, str))
                        else value["score"]
                    )
                elif isinstance(value, (int, float)):
                    result["scores"][key] = value
    elif "criteria_scores" in parsed:
        # Handle Claude's alternate format
        criteria = parsed["criteria_scores"]
        if isinstance(criteria, dict):
            for key, value in criteria.items():
                if isinstance(value, dict) and "score" in value:
                    result["scores"][key] = value["score"]
                elif isinstance(value, (int, float)):
                    result["scores"][key] = value

    # Extract total score
    if "total" in parsed and parsed["total"] is not None:
        result["total"] = (
            float(parsed["total"]) if isinstance(parsed["total"], (int, float)) else None
        )
    elif "score" in parsed and isinstance(parsed["score"], (int, float)):
        result["total"] = float(parsed["score"])
    elif "overall_score" in parsed and isinstance(parsed["overall_score"], (int, float)):
        result["total"] = float(parsed["overall_score"])
    elif result["scores"]:
        # Calculate average if we have individual scores but no total
        values = [v for v in result["scores"].values() if isinstance(v, (int, float))]
        if values:
            result["total"] = sum(values) / len(values)

    # Some judge models return a summed total across criteria even though each
    # criterion is scored on a 0..1 scale. Normalize that back to a 0..1 mean.
    values = [v for v in result["scores"].values() if isinstance(v, (int, float))]
    if (
        values
        and result["total"] is not None
        and result["total"] > 1.0
        and all(0.0 <= float(v) <= 1.0 for v in values)
    ):
        result["total"] = sum(values) / len(values)

    # Extract notes/justification
    if "notes" in parsed:
        result["notes"] = str(parsed["notes"])
    elif "justification" in parsed:
        result["notes"] = str(parsed["justification"])
    elif "reasoning" in parsed:
        result["notes"] = str(parsed["reasoning"])

    return result
