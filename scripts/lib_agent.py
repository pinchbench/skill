"""
OpenClaw agent execution helpers for PinchBench.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import stat
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request

from lib_tasks import Task
from lib_fws import is_fws_task, fws_available, start_fws, stop_fws


logger = logging.getLogger(__name__)

USE_SHELL = platform.system() == "Windows"


class ModelValidationError(Exception):
    """Raised when a model ID is invalid or inaccessible."""

    pass


MAX_OPENCLAW_MESSAGE_CHARS = int(os.environ.get("PINCHBENCH_MAX_MSG_CHARS", "8000"))
JUDGE_MAX_MSG_CHARS = int(os.environ.get("PINCHBENCH_JUDGE_MAX_MSG_CHARS", "3000"))


def _coerce_subprocess_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


# Thinking levels supported by OpenClaw
# See: https://docs.openclaw.ai/tools/thinking
THINKING_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "adaptive")

# Models that support xhigh thinking level (high reasoning budget)
# Sourced from OpenClaw src/auto-reply/thinking.ts XHIGH_MODEL_REFS
XHIGH_MODELS = {
    # OpenAI
    "openai/gpt-5.4",
    "openai/gpt-5.4-pro",
    "openai/gpt-5.2",
    # OpenAI Codex
    "openai-codex/gpt-5.4",
    "openai-codex/gpt-5.3-codex",
    "openai-codex/gpt-5.3-codex-spark",
    "openai-codex/gpt-5.2-codex",
    "openai-codex/gpt-5.1-codex",
    # GitHub Copilot
    "github-copilot/gpt-5.2-codex",
    "github-copilot/gpt-5.2",
}

XHIGH_MODELS_LOWER = {model.lower() for model in XHIGH_MODELS}
XHIGH_MODEL_IDS_LOWER = {model.split("/")[-1].lower() for model in XHIGH_MODELS}

# Adaptive thinking is currently provider-managed for Anthropic Claude 4.6 models.
ADAPTIVE_PROVIDER = "anthropic"
ADAPTIVE_MODEL_PREFIXES = (
    "claude-opus-4-6",
    "claude-opus-4.6",
    "claude-sonnet-4-6",
    "claude-sonnet-4.6",
)


def slugify_model(model_id: str) -> str:
    return model_id.replace("/", "-").replace(".", "-").lower()


def validate_openrouter_model(model_id: str, timeout_seconds: float = 10.0) -> bool:
    """
    Validate that a model ID exists on OpenRouter.

    Args:
        model_id: Model ID (with or without openrouter/ prefix)
        timeout_seconds: HTTP request timeout

    Returns:
        True if model is valid and accessible

    Raises:
        ModelValidationError: If model doesn't exist or validation fails
    """
    # Strip openrouter/ prefix if present
    bare_model_id = model_id
    if bare_model_id.startswith("openrouter/"):
        bare_model_id = bare_model_id[len("openrouter/") :]

    # Skip validation for non-OpenRouter models
    if "/" not in bare_model_id:
        logger.info("Skipping model validation for non-OpenRouter model: %s", model_id)
        return True

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set, skipping model validation")
        return True

    logger.info("🔍 Validating model: %s", bare_model_id)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://pinchbench.com",
        "X-Title": "PinchBench",
    }

    # First, try the specific model endpoint (fast path for valid models)
    encoded_model_id = bare_model_id.replace("/", "%2F")
    specific_endpoint = f"https://openrouter.ai/api/v1/models/{encoded_model_id}"
    req = request.Request(specific_endpoint, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            # Model exists - validation passed
            logger.info("✅ Model validated: %s", bare_model_id)
            return True
    except error.HTTPError as exc:
        if exc.code == 404:
            # Model not found - fall through to fetch full catalog for suggestions
            pass
        else:
            logger.warning("OpenRouter API error during validation: %s", exc)
            return True
    except error.URLError as exc:
        logger.warning("Network error during model validation: %s", exc)
        return True

    # Model not found - fetch full catalog for "did you mean" suggestions
    catalog_endpoint = "https://openrouter.ai/api/v1/models"
    req = request.Request(catalog_endpoint, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        logger.warning("OpenRouter API error fetching model catalog: %s", exc)
        raise ModelValidationError(f"Model '{bare_model_id}' not found on OpenRouter.")
    except error.URLError as exc:
        logger.warning("Network error fetching model catalog: %s", exc)
        raise ModelValidationError(f"Model '{bare_model_id}' not found on OpenRouter.")
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse OpenRouter response: %s", exc)
        raise ModelValidationError(f"Model '{bare_model_id}' not found on OpenRouter.")

    models = data.get("data", [])
    model_ids = {
        mid
        for m in models
        if isinstance(m, dict)
        for mid in [m.get("id")]
        if isinstance(mid, str) and mid
    }

    # Some OpenRouter model detail lookups intermittently return 404 for valid
    # IDs. Treat an exact catalog hit as authoritative to avoid false negatives.
    if bare_model_id in model_ids:
        logger.info("✅ Model validated via catalog fallback: %s", bare_model_id)
        return True

    # Check for close matches (typos)
    close_matches = []
    bare_lower = bare_model_id.lower()
    for mid in model_ids:
        mid_lower = mid.lower()
        if mid_lower == bare_lower:
            continue
        if bare_lower in mid_lower or mid_lower in bare_lower:
            close_matches.append(mid)

    error_msg = f"Model '{bare_model_id}' not found on OpenRouter."
    if close_matches:
        close_matches_str = ", ".join(sorted(close_matches)[:5])
        error_msg += f" Did you mean: {close_matches_str}?"
    else:
        # Try to suggest based on provider
        provider = bare_model_id.split("/")[0] if "/" in bare_model_id else None
        if provider:
            provider_models = [m for m in model_ids if m.startswith(f"{provider}/")]
            if provider_models:
                error_msg += (
                    f" Available {provider} models: {', '.join(sorted(provider_models)[:5])}"
                )

    raise ModelValidationError(error_msg)


def supports_xhigh_thinking(model_id: str) -> bool:
    """Check if a model supports xhigh thinking level."""
    normalized = slugify_model(model_id)
    model_lower = model_id.lower()
    xhigh_models_lower = {m.lower() for m in XHIGH_MODELS}
    if normalized in xhigh_models_lower:
        return True
    parts = normalized.split("/")
    if len(parts) == 3 and parts[0] == "openrouter":
        provider_model = f"{parts[1]}/{parts[2]}"
        if provider_model in xhigh_models_lower:
            return True
    if "/" not in model_id:
        return model_lower in xhigh_models_lower
    return False


def supports_adaptive_thinking(model_id: str) -> bool:
    """Check if a model natively supports adaptive thinking."""
    normalized = slugify_model(model_id)
    parts = normalized.split("/")
    adaptive_provider = "anthropic"
    adaptive_prefixes = ("claude-4.6",)
    if len(parts) == 3 and parts[0] == "openrouter":
        provider = parts[1]
        model = parts[2]
    elif len(parts) >= 2:
        provider = parts[-2]
        model = parts[-1]
    else:
        return False
    if provider != adaptive_provider:
        return False
    return any(model.startswith(prefix) for prefix in adaptive_prefixes)


def validate_thinking_level(level: str, model_id: Optional[str] = None) -> Optional[str]:
    """
    Validate a thinking level and check model compatibility.

    Args:
        level: The thinking level to validate
        model_id: Optional model ID to check xhigh compatibility

    Returns:
        The validated level, or None if invalid
    """
    level_lower = level.lower().strip()
    if level_lower not in THINKING_LEVELS:
        logger.warning(
            "Invalid thinking level '%s'. Valid levels: %s",
            level,
            ", ".join(THINKING_LEVELS),
        )
        return None
    if level_lower == "xhigh" and model_id and not supports_xhigh_thinking(model_id):
        logger.warning(
            "Thinking level 'xhigh' not supported by model '%s'. "
            "xhigh is only available for GPT-5.x model families.",
            model_id,
        )
        return None
    if level_lower == "adaptive" and model_id and not supports_adaptive_thinking(model_id):
        logger.warning(
            "Thinking level 'adaptive' is not natively supported by model '%s'. "
            "adaptive is currently intended for Anthropic Claude 4.6 models.",
            model_id,
        )
        return None
    return level_lower


def _get_agent_workspace(agent_id: str) -> Path | None:
    """Get the workspace path for an agent from OpenClaw config."""
    try:
        list_result = subprocess.run(
            ["openclaw", "agents", "list"],
            capture_output=True,
            text=True,
            check=False,
            shell=USE_SHELL,
        )
        if list_result.returncode != 0:
            return None

        # Parse the agent list output to find workspace
        # OpenClaw normalizes colons to dashes and lowercases agent names
        normalized_id = agent_id.replace(":", "-").lower()
        lines = list_result.stdout.split("\n")
        found_agent = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"- {agent_id}") or stripped.startswith(f"- {normalized_id}"):
                found_agent = True
            elif found_agent and "Workspace:" in line:
                workspace_str = line.split("Workspace:")[1].strip()
                # Expand ~ if present
                if workspace_str.startswith("~/"):
                    workspace_str = str(Path.home() / workspace_str[2:])
                return Path(workspace_str)
            elif found_agent and line.strip().startswith("-"):
                # Found next agent, stop looking
                break
        return None
    except Exception as exc:
        logger.warning("Failed to get agent workspace: %s", exc)
        return None


def ensure_agent_exists(
    agent_id: str,
    model_id: str,
    workspace_dir: Path,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> bool:
    """Ensure the OpenClaw agent exists with the correct workspace.

    If the agent already exists but points to a different workspace, it is
    deleted and recreated so that the new workspace takes effect.

    When *base_url* is provided, a custom OpenAI-compatible provider is
    configured in the agent's ``models.json`` instead of relying on
    OpenRouter.  *api_key* defaults to ``${OPENAI_API_KEY}`` (resolved by
    OpenClaw at runtime) if not given.

    Returns True if the agent was (re)created.
    """
    workspace_dir.mkdir(parents=True, exist_ok=True)

    try:
        list_result = subprocess.run(
            ["openclaw", "agents", "list"],
            capture_output=True,
            text=True,
            check=False,
            shell=USE_SHELL,
        )
    except FileNotFoundError:
        logger.error("openclaw CLI not found while listing agents")
        return False

    if list_result.returncode == 0:
        # Check for exact agent ID match — avoid substring false positives
        # (e.g. "bench-foo-4" matching "bench-foo-4-5" in the output).
        # Output format is "- <agent_id>" or "- <agent_id> (default)" per line.
        # OpenClaw normalizes colons to dashes in directory/display names, so
        # also check the normalized form.
        existing_agents = set()
        for line in list_result.stdout.splitlines():
            line = line.strip()
            if line.startswith("- "):
                # Extract agent name: "- bench-foo-4-5" or "- main (default)"
                name_part = line[2:].split()[0] if line[2:].strip() else ""
                if name_part:
                    existing_agents.add(name_part.lower())
        normalized_id = agent_id.replace(":", "-").lower()
        if agent_id.lower() in existing_agents or normalized_id in existing_agents:
            # Agent exists — check if workspace matches
            current_workspace = _get_agent_workspace(agent_id)
            if (
                current_workspace is not None
                and current_workspace.resolve() == workspace_dir.resolve()
            ):
                logger.info("Agent %s already exists with correct workspace", agent_id)
                return False
            # Workspace is stale or unknown — delete and recreate
            delete_name = normalized_id if normalized_id in existing_agents else agent_id
            logger.info(
                "Agent %s exists with stale workspace (%s != %s), recreating",
                agent_id,
                current_workspace,
                workspace_dir,
            )
            subprocess.run(
                ["openclaw", "agents", "delete", delete_name, "--force"],
                capture_output=True,
                text=True,
                check=False,
            shell=USE_SHELL,
            )

    logger.info("Creating OpenClaw agent %s", agent_id)
    try:
        create_result = subprocess.run(
            [
                "openclaw",
                "agents",
                "add",
                agent_id,
                "--model",
                model_id,
                "--workspace",
                str(workspace_dir),
                "--non-interactive",
            ],
            capture_output=True,
            text=True,
            check=False,
            shell=USE_SHELL,
        )
    except FileNotFoundError:
        logger.error("openclaw CLI not found while creating agent")
        return False

    if create_result.returncode != 0:
        logger.warning(
            "Agent creation returned %s: %s", create_result.returncode, create_result.stderr
        )

    # Configure models.json for the bench agent
    bench_agent_dir = _get_agent_store_dir(agent_id) / "agent"
    bench_agent_dir.mkdir(parents=True, exist_ok=True)
    bench_models = bench_agent_dir / "models.json"
    main_models = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "models.json"

    if base_url:
        # Custom OpenAI-compatible endpoint — build a provider entry
        data: dict[str, Any] = {}
        if main_models.exists():
            try:
                data = json.loads(main_models.read_text("utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                data = {}

        key_ref = api_key if api_key else "${OPENAI_API_KEY}"
        providers = data.setdefault("models", {}).setdefault("providers", {})
        data["models"]["mode"] = "merge"
        providers["custom"] = {
            "baseUrl": base_url,
            "apiKey": key_ref,
            "api": "openai-completions",
            "models": [
                {
                    "id": model_id,
                    "name": model_id,
                    "reasoning": False,
                    "input": ["text"],
                    "contextWindow": 200000,
                    "maxTokens": 8192,
                }
            ],
        }
        data["defaultProvider"] = "custom"
        data["defaultModel"] = model_id
        bench_models.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        logger.info(
            "Configured custom provider (%s) with model %s for agent %s",
            base_url,
            model_id,
            agent_id,
        )
    elif main_models.exists():
        # Standard OpenRouter flow — copy main's models.json and set defaults
        import shutil as _shutil
        _shutil.copy2(main_models, bench_models)
        if "/" in model_id:
            provider_name, model_name = model_id.split("/", 1)
            try:
                raw = bench_models.read_text("utf-8-sig")
                data = json.loads(raw)
                data["defaultProvider"] = provider_name
                data["defaultModel"] = model_name
                bench_models.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), "utf-8"
                )
                logger.info(
                    "Set bench agent default model to %s / %s", provider_name, model_name
                )
            except Exception as exc:
                logger.warning("Failed to set default model in bench models.json: %s", exc)
        logger.info("Copied main agent models.json to bench agent %s", agent_id)

    # Delete sessions.json so OpenClaw picks up the new defaultProvider/defaultModel
    # instead of reusing a cached session entry that still points to an old model.
    bench_sessions_dir = _get_agent_store_dir(agent_id) / "sessions"
    sessions_store = bench_sessions_dir / "sessions.json"
    if sessions_store.exists():
        try:
            sessions_store.unlink()
            logger.info("Deleted stale sessions.json for bench agent %s", agent_id)
        except OSError as exc:
            logger.warning("Failed to delete sessions.json: %s", exc)

    return True


def cleanup_agent_sessions(agent_id: str) -> None:
    """Remove stored session transcripts for an agent to avoid unbounded growth."""
    agent_dir = _get_agent_store_dir(agent_id)
    sessions_dir = agent_dir / "sessions"
    if not sessions_dir.exists():
        return
    removed = 0
    for pattern in ("*.jsonl", "*.jsonl.lock", "*.ndjson"):
        for path in sessions_dir.rglob(pattern):
            try:
                path.unlink()
                removed += 1
            except OSError as exc:
                logger.warning("Failed to remove session file %s: %s", path, exc)
    sessions_store = sessions_dir / "sessions.json"
    if sessions_store.exists():
        try:
            sessions_store.unlink()
        except OSError as exc:
            logger.warning("Failed to remove session store %s: %s", sessions_store, exc)
    if removed:
        logger.info("Removed %s old OpenClaw session transcripts for %s", removed, agent_id)


def prepare_task_workspace(skill_dir: Path, run_id: str, task: Task, agent_id: str) -> Path:
    """
    Prepare workspace for a task by copying fixtures.
    Uses the agent's configured workspace to ensure files are in the right place.
    """
    import shutil

    # Get agent's workspace from agent config
    workspace = _get_agent_workspace(agent_id)
    if workspace is None:
        # Fallback to task-specific workspace if agent workspace not found
        logger.warning("Could not find agent workspace, using fallback")
        workspace = Path(f"/tmp/pinchbench/{run_id}/{task.task_id}")

    _BOOTSTRAP_FILES = ["SOUL.md", "BOOTSTRAP.md", "USER.md", "IDENTITY.md", "HEARTBEAT.md", "TOOLS.md"]

    def _remove_readonly(func, path, _):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass

    saved_bootstrap: dict[str, bytes] = {}
    if workspace.exists():
        for fname in _BOOTSTRAP_FILES:
            fpath = workspace / fname
            if fpath.exists():
                saved_bootstrap[fname] = fpath.read_bytes()
        shutil.rmtree(workspace, onerror=_remove_readonly)
    workspace.mkdir(parents=True, exist_ok=True)

    for fname, content in saved_bootstrap.items():
        (workspace / fname).write_bytes(content)

    for file_spec in task.workspace_files:
        if "content" in file_spec:
            dest = workspace / file_spec["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(file_spec["content"])
            continue

        source = skill_dir / "assets" / file_spec["source"]
        dest = workspace / file_spec["dest"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(source.read_bytes())
        except FileNotFoundError:
            logger.error("Workspace file not found: %s", source)
            raise

    # Copy skills from main workspace to benchmark workspace
    # This enables benchmark agents to use installed skills like nano-pdf
    main_skills_dir = Path.home() / ".openclaw" / "workspace" / "skills"
    if main_skills_dir.exists():
        dest_skills_dir = workspace / "skills"
        dest_skills_dir.mkdir(parents=True, exist_ok=True)
        for skill_dir_src in main_skills_dir.iterdir():
            if skill_dir_src.is_dir():
                dest_skill_dir = dest_skills_dir / skill_dir_src.name
                # Copy skill directory
                import shutil

                if dest_skill_dir.exists():
                    shutil.rmtree(dest_skill_dir, onerror=_remove_readonly)
                shutil.copytree(skill_dir_src, dest_skill_dir)
                logger.info("Copied skill to benchmark workspace: %s", skill_dir_src.name)

    return workspace


def _get_agent_store_dir(agent_id: str) -> Path:
    base_dir = Path.home() / ".openclaw" / "agents"
    # OpenClaw normalizes agent IDs to lowercase and replaces colons with dashes
    normalized_id = agent_id.replace(":", "-").lower()
    direct_dir = base_dir / agent_id
    if direct_dir.exists():
        return direct_dir
    normalized_dir = base_dir / normalized_id
    if normalized_dir.exists():
        return normalized_dir
    return direct_dir


def _resolve_session_id_from_store(agent_id: str) -> str | None:
    agent_dir = _get_agent_store_dir(agent_id)
    sessions_store = agent_dir / "sessions" / "sessions.json"
    if not sessions_store.exists():
        return None
    try:
        sessions_payload = json.loads(sessions_store.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse sessions store: %s", exc)
        return None
    if not isinstance(sessions_payload, dict):
        return None

    normalized_id = agent_id.replace(":", "-").lower()
    preferred_keys = [
        f"agent:{agent_id}:main",
        f"agent:{agent_id}:default",
        f"agent:{normalized_id}:main",
        f"agent:{normalized_id}:default",
    ]
    for key in preferred_keys:
        entry = sessions_payload.get(key)
        if isinstance(entry, dict) and entry.get("sessionId"):
            return entry["sessionId"]

    newest_entry = None
    newest_timestamp = -1
    for entry in sessions_payload.values():
        if not isinstance(entry, dict):
            continue
        if "sessionId" not in entry:
            continue
        updated_at = entry.get("updatedAt")
        if isinstance(updated_at, (int, float)) and updated_at > newest_timestamp:
            newest_timestamp = updated_at
            newest_entry = entry
    if newest_entry:
        return newest_entry.get("sessionId")
    return None


def _find_transcript_path_from_sessions_store(
    agent_id: str, started_at: float = 0.0, tolerance_seconds: float = 5.0
) -> Optional[Path]:
    """Best-effort transcript path resolution from sessions.json payload values.

    Only returns paths whose mtime is >= started_at - tolerance_seconds so that
    a stale session written by a previous task's async tail (after its transcript
    was already archived) is never mistaken for the current task's session.
    """
    agent_dir = _get_agent_store_dir(agent_id)
    sessions_store = agent_dir / "sessions" / "sessions.json"
    if not sessions_store.exists():
        return None
    try:
        payload = json.loads(sessions_store.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    def _iter_strings(node: Any):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for value in node.values():
                yield from _iter_strings(value)
        elif isinstance(node, list):
            for value in node:
                yield from _iter_strings(value)

    suffixes = (".jsonl", ".ndjson")
    session_root = agent_dir / "sessions"
    min_mtime = started_at - tolerance_seconds
    for value in _iter_strings(payload):
        if not value.endswith(suffixes):
            continue
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = session_root / value
        if candidate.exists() and candidate.stat().st_mtime >= min_mtime:
            return candidate
    return None


def _find_recent_session_path(agent_dir: Path, started_at: float) -> Path | None:
    sessions_dir = agent_dir / "sessions"
    if not sessions_dir.exists():
        return None
    candidates = list(sessions_dir.rglob("*.jsonl")) + list(sessions_dir.rglob("*.ndjson"))
    if not candidates:
        return None
    tolerance_seconds = 5.0
    recent_candidates = [
        path for path in candidates if path.stat().st_mtime >= (started_at - tolerance_seconds)
    ]
    pool = recent_candidates or candidates
    return max(pool, key=lambda path: path.stat().st_mtime)


def _load_transcript(
    agent_id: str, session_id: str, started_at: float
) -> tuple[List[Dict[str, Any]], Optional[Path]]:
    agent_dir = _get_agent_store_dir(agent_id)
    transcript_path = None

    # OpenClaw ignores the --session-id we pass and generates its own UUID-based
    # session ID internally.  We need to discover the actual transcript path.
    #
    # Strategy (with retries to handle write-delay):
    #   1. Resolve the real session ID from sessions.json
    #   2. Glob for any .jsonl in the sessions dir (most-recently-modified)
    #   3. Try our passed-in session ID as a last resort
    for attempt in range(15):
        # 1. Try sessions.json first — OpenClaw writes the real UUID here
        resolved_session_id = _resolve_session_id_from_store(agent_id)
        if resolved_session_id:
            session_dir = agent_dir / "sessions"
            for candidate in (
                session_dir / f"{resolved_session_id}.jsonl",
                session_dir / f"{resolved_session_id}.ndjson",
                session_dir / resolved_session_id / "transcript.jsonl",
                session_dir / resolved_session_id / "events.jsonl",
            ):
                if candidate.exists():
                    transcript_path = candidate
                    logger.info(
                        "Found transcript via sessions.json: %s (attempt %s)",
                        candidate.name,
                        attempt + 1,
                    )
                    break
            if transcript_path is not None:
                break

        # 1b. Parse transcript-like paths from sessions.json values
        candidate_from_store = _find_transcript_path_from_sessions_store(agent_id, started_at)
        if candidate_from_store is not None:
            transcript_path = candidate_from_store
            logger.info(
                "Found transcript via sessions.json path: %s (attempt %s)",
                candidate_from_store,
                attempt + 1,
            )
            break

        # 2. Glob fallback — pick the most recently modified .jsonl
        recent_path = _find_recent_session_path(agent_dir, started_at)
        if recent_path is not None:
            transcript_path = recent_path
            logger.info(
                "Found transcript via glob fallback: %s (attempt %s)",
                recent_path.name,
                attempt + 1,
            )
            break

        # 3. Try our passed-in session ID (unlikely to work, but check anyway)
        for direct_path in (
            agent_dir / "sessions" / f"{session_id}.jsonl",
            agent_dir / "sessions" / f"{session_id}.ndjson",
        ):
            if direct_path.exists():
                transcript_path = direct_path
                logger.info(
                    "Found transcript via passed session ID: %s (attempt %s)",
                    direct_path.name,
                    attempt + 1,
                )
                break
        if transcript_path is not None:
            break

        if attempt < 14:
            time.sleep(1.0)

    if transcript_path is None:
        sessions_dir = agent_dir / "sessions"
        if sessions_dir.exists():
            all_files = list(sessions_dir.iterdir())
            logger.warning(
                "Transcript not found for agent %s. Sessions dir contents: %s",
                agent_id,
                [f.name for f in all_files],
            )
            sessions_store = sessions_dir / "sessions.json"
            if sessions_store.exists():
                try:
                    payload_preview = sessions_store.read_text(encoding="utf-8")[:1200]
                    logger.warning("sessions.json preview: %s", payload_preview)
                except OSError as exc:
                    logger.warning("Could not read sessions.json preview: %s", exc)
        else:
            logger.warning(
                "Transcript not found — sessions dir does not exist: %s",
                sessions_dir,
            )
        return [], None

    transcript: List[Dict[str, Any]] = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            transcript.append(json.loads(line))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse transcript line: %s", exc)
            transcript.append({"raw": line, "parse_error": str(exc)})
    return transcript, transcript_path


def _extract_usage_from_transcript(transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum token usage and cost from all assistant messages in transcript."""
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "request_count": 0,
    }

    for entry in transcript:
        if entry.get("type") != "message":
            continue
        msg = entry.get("message", {})
        if msg.get("role") != "assistant":
            continue
        totals["request_count"] += 1
        usage = msg.get("usage", {})
        totals["input_tokens"] += usage.get("input", 0)
        totals["output_tokens"] += usage.get("output", 0)
        totals["cache_read_tokens"] += usage.get("cacheRead", 0)
        totals["cache_write_tokens"] += usage.get("cacheWrite", 0)
        totals["total_tokens"] += usage.get("totalTokens", 0)
        cost = usage.get("cost", {})
        totals["cost_usd"] += cost.get("total", 0.0)

    return totals


def execute_openclaw_task(
    *,
    task: Task,
    agent_id: str,
    model_id: str,
    run_id: str,
    timeout_multiplier: float,
    skill_dir: Path,
    output_dir: Optional[Path] = None,
    verbose: bool = False,
    thinking_level: str | None = None,
) -> Dict[str, Any]:
    logger.info("🤖 Agent [%s] starting task: %s", agent_id, task.task_id)
    logger.info("   Task: %s", task.name)
    logger.info("   Category: %s", task.category)
    if verbose:
        logger.info(
            "   Prompt: %s", task.prompt[:500] + "..." if len(task.prompt) > 500 else task.prompt
        )
    if thinking_level:
        logger.info("   Thinking: %s", thinking_level)

    # Clean up previous session transcripts so we can reliably find this task's
    # transcript (OpenClaw uses its own UUID-based naming, not our session ID).
    cleanup_agent_sessions(agent_id)

    # Start fws server for GWS tasks
    fws_env = None
    if is_fws_task(task.frontmatter):
        if not fws_available():
            logger.warning("⚠️ Task %s requires fws but it's not installed (npm install -g @juppytt/fws)", task.task_id)
        else:
            fws_env = start_fws()

    # Use --local for fws tasks so env vars propagate to the agent
    use_local = fws_env is not None

    start_time = time.time()
    workspace = prepare_task_workspace(skill_dir, run_id, task, agent_id)
    session_id = f"{task.task_id}_{int(time.time() * 1000)}"
    timeout_seconds = task.timeout_seconds * timeout_multiplier
    stdout = ""
    stderr = ""
    exit_code = -1
    timed_out = False

    # Check if this is a multi-session task
    sessions = task.frontmatter.get("sessions", [])
    if sessions:
        # Multi-session task: send each prompt in sequence
        logger.info("📋 Multi-session task with %d sessions", len(sessions))
        for i, session_entry in enumerate(sessions, 1):
            # Extract prompt text from session entry (handle both string and dict formats)
            if isinstance(session_entry, str):
                session_prompt = session_entry
            elif isinstance(session_entry, dict):
                session_prompt = session_entry.get("prompt") or session_entry.get("message", "")
            else:
                logger.warning("⚠️ Skipping invalid session entry: %s", session_entry)
                continue

            logger.info("   Session %d/%d", i, len(sessions))
            elapsed = time.time() - start_time
            remaining = timeout_seconds - elapsed
            if remaining <= 0:
                timed_out = True
                break
            try:
                cmd = [
                    "openclaw",
                    "agent",
                    "--agent",
                    agent_id,
                    "--session-id",
                    session_id,
                    "--message",
                    session_prompt,
                ]
                if thinking_level:
                    cmd.extend(["--thinking", thinking_level])
                if use_local:
                    cmd.insert(2, "--local")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(workspace),
                    timeout=remaining,
                    check=False,
                    shell=USE_SHELL,
                )
                stdout += result.stdout
                stderr += result.stderr
                exit_code = result.returncode
                if result.returncode not in (0, -1):
                    break
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stdout += _coerce_subprocess_output(exc.stdout)
                stderr += _coerce_subprocess_output(exc.stderr)
                break
            except FileNotFoundError as exc:
                stderr = f"openclaw command not found: {exc}"
                break
    else:
        # Single-session task: send task.prompt once
        try:
            cmd = [
                "openclaw",
                "agent",
                "--agent",
                agent_id,
                "--session-id",
                session_id,
                "--message",
                task.prompt,
            ]
            if thinking_level:
                cmd.extend(["--thinking", thinking_level])
            if use_local:
                cmd.insert(2, "--local")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(workspace),
                timeout=timeout_seconds,
                check=False,
                shell=USE_SHELL,
            )
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = _coerce_subprocess_output(exc.stdout)
            stderr = _coerce_subprocess_output(exc.stderr)
        except FileNotFoundError as exc:
            stderr = f"openclaw command not found: {exc}"

    transcript, transcript_path = _load_transcript(agent_id, session_id, start_time)
    usage = _extract_usage_from_transcript(transcript)
    execution_time = time.time() - start_time

    # Archive the raw transcript JSONL before cleanup_agent_sessions deletes it
    if transcript_path and output_dir:
        import shutil as _shutil
        output_dir.mkdir(parents=True, exist_ok=True)
        archive_dest = output_dir / f"{task.task_id}.jsonl"
        try:
            _shutil.copy2(transcript_path, archive_dest)
            logger.info("Archived transcript to %s", archive_dest)
        except OSError as exc:
            logger.warning("Failed to archive transcript: %s", exc)

    status = "success"
    if timed_out:
        status = "timeout"
    if not transcript:
        status = "error"
    if exit_code not in (0, -1) and not timed_out:
        status = "error"
    if stderr and "openclaw command not found" in str(stderr):
        status = "error"

    # Verbose logging for debugging
    if verbose:
        logger.info("   [VERBOSE] Exit code: %s", exit_code)
        logger.info("   [VERBOSE] Execution time: %.2fs", execution_time)
        logger.info("   [VERBOSE] Workspace: %s", workspace)
        if stdout:
            logger.info("   [VERBOSE] Stdout (first 1000 chars):\n%s", stdout[:1000])
        if stderr:
            logger.info("   [VERBOSE] Stderr:\n%s", stderr[:1000])
        logger.info("   [VERBOSE] Transcript entries: %d", len(transcript))

        # Show agent responses from transcript
        for entry in transcript:
            if entry.get("type") == "message":
                msg = entry.get("message", {})
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "assistant":
                    # Truncate long responses
                    preview = content[:500] + "..." if len(content) > 500 else content
                    logger.info("   [VERBOSE] Agent response: %s", preview)
                elif role == "user":
                    preview = content[:200] + "..." if len(content) > 200 else content
                    logger.info("   [VERBOSE] User message: %s", preview)

        # Show workspace files after task
        if workspace.exists():
            logger.info("   [VERBOSE] Workspace files after task:")
            for f in sorted(workspace.rglob("*")):
                if f.is_file():
                    try:
                        size = f.stat().st_size
                        logger.info("      %s (%d bytes)", f.relative_to(workspace), size)
                    except OSError:
                        logger.info("      %s", f.relative_to(workspace))

    # Stop fws mock server if we started it
    if fws_env is not None:
        stop_fws(fws_env)

    return {
        "agent_id": agent_id,
        "task_id": task.task_id,
        "thinking_level": thinking_level,
        "status": status,
        "transcript": transcript,
        "usage": usage,
        "workspace": str(workspace),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "execution_time": execution_time,
        "stdout": stdout,
        "stderr": stderr,
    }


def run_openclaw_prompt(
    *,
    agent_id: str,
    prompt: str,
    workspace: Path,
    timeout_seconds: float,
    thinking_level: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a single OpenClaw prompt for helper agents like the judge."""
    cleanup_agent_sessions(agent_id)

    agent_workspace = _get_agent_workspace(agent_id)
    if agent_workspace and agent_workspace.exists():
        for bootstrap_file in ["BOOTSTRAP.md", "SOUL.md", "USER.md", "IDENTITY.md", "HEARTBEAT.md"]:
            bp = agent_workspace / bootstrap_file
            if bp.exists():
                try:
                    bp.unlink()
                    logger.debug("Removed bootstrap file from judge workspace: %s", bootstrap_file)
                except OSError as exc:
                    logger.warning("Failed to remove bootstrap file %s: %s", bootstrap_file, exc)

    start_time = time.time()
    workspace.mkdir(parents=True, exist_ok=True)
    session_id = f"judge_{int(time.time() * 1000)}"
    stdout = ""
    stderr = ""
    exit_code = -1
    timed_out = False

    chunks = [
        prompt[i : i + JUDGE_MAX_MSG_CHARS]
        for i in range(0, max(1, len(prompt)), JUDGE_MAX_MSG_CHARS)
    ]
    if len(chunks) > 1:
        total_chunks = len(chunks)
        chunks = [
            (
                f"You are receiving a long prompt in {total_chunks} parts.\n"
                f"Ignore and do not respond until the final part.\n\n"
                f"Part 1/{total_chunks}:\n{chunks[0]}"
            )
        ] + [
            (
                f"Part {i + 2}/{total_chunks}:\n{chunks[i + 1]}"
                if i + 2 < total_chunks
                else (
                    f"Part {i + 2}/{total_chunks} (final):\n{chunks[i + 1]}\n"
                    "All parts received. Proceed with final judgment now."
                )
            )
            for i in range(0, total_chunks - 1)
        ]
    for chunk in chunks:
        elapsed = time.time() - start_time
        remaining = timeout_seconds - elapsed
        if remaining <= 0:
            timed_out = True
            break
        try:
            openclaw_path = os.environ.get("OPENCLAW_PATH", "openclaw")
            send_chunk = (
                chunk.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
                if USE_SHELL
                else chunk
            )
            cmd = [
                openclaw_path,
                "agent",
                "--agent",
                agent_id,
                "--session-id",
                session_id,
                "--message",
                send_chunk,
            ]
            if thinking_level:
                cmd.extend(["--thinking", thinking_level])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(workspace),
                timeout=remaining,
                check=False,
                shell=USE_SHELL,
            )
            stdout += result.stdout
            stderr += result.stderr
            exit_code = result.returncode
            if result.returncode not in (0, -1) and not timed_out:
                break
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout += _coerce_subprocess_output(exc.stdout)
            stderr += _coerce_subprocess_output(exc.stderr)
            break
        except FileNotFoundError as exc:
            stderr += f"openclaw command not found: {exc}"
            break

    transcript, _ = _load_transcript(agent_id, session_id, start_time)
    execution_time = time.time() - start_time

    status = "success"
    if timed_out:
        status = "timeout"
    if not transcript:
        status = "error"
    if exit_code not in (0, -1) and not timed_out:
        status = "error"
    if stderr and "openclaw command not found" in str(stderr):
        status = "error"

    return {
        "agent_id": agent_id,
        "status": status,
        "transcript": transcript,
        "workspace": str(workspace),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "execution_time": execution_time,
        "stdout": stdout,
        "stderr": stderr,
    }


_JUDGE_SYSTEM_MSG = (
    "You are a strict grading function. "
    "Respond with ONLY a JSON object, no prose, no markdown fences, no extra text."
)


def call_judge_api(
    *,
    prompt: str,
    model: str,
    timeout_seconds: float = 120.0,
) -> Dict[str, Any]:
    """Call a judge model directly via API, bypassing OpenClaw.

    Dispatches based on model prefix:
      - openrouter/* -> OpenRouter chat completions API
      - anthropic/*  -> Anthropic Messages API
      - openai/*     -> OpenAI chat completions API
      - claude       -> headless Claude CLI (claude -p)

    Returns {"status": str, "text": str, "error"?: str}.
    """
    if model == "claude" or model.startswith("claude:"):
        return _judge_via_claude_cli(prompt, model, timeout_seconds)
    if model.startswith("anthropic/"):
        return _judge_via_anthropic(prompt, model, timeout_seconds)
    if model.startswith("openai/"):
        return _judge_via_openai(prompt, model, timeout_seconds)
    # Default: OpenRouter (handles openrouter/ prefix and bare provider/model)
    return _judge_via_openrouter(prompt, model, timeout_seconds)


def _judge_via_openai_compat(
    prompt: str,
    api_model: str,
    endpoint: str,
    api_key: str,
    timeout_seconds: float,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Shared implementation for OpenAI-compatible chat completions APIs."""
    payload = json.dumps({
        "model": api_model,
        "messages": [
            {"role": "system", "content": _JUDGE_SYSTEM_MSG},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_completion_tokens": 2048,
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    req = request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        logger.error("Judge API error (%s): %s", exc.code, body)
        return {"status": "error", "text": "", "error": f"HTTP {exc.code}: {body}"}
    except error.URLError as exc:
        logger.error("Judge network error: %s", exc)
        return {"status": "error", "text": "", "error": str(exc)}
    except TimeoutError:
        return {"status": "timeout", "text": "", "error": "Request timed out"}

    choices = data.get("choices", [])
    if not choices:
        return {"status": "error", "text": "", "error": "No choices in response"}
    text = choices[0].get("message", {}).get("content", "")
    return {"status": "success", "text": text}


def _judge_via_openrouter(prompt: str, model: str, timeout_seconds: float) -> Dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"status": "error", "text": "", "error": "OPENROUTER_API_KEY not set"}
    bare_model = model.removeprefix("openrouter/")
    return _judge_via_openai_compat(
        prompt, bare_model,
        "https://openrouter.ai/api/v1/chat/completions",
        api_key, timeout_seconds,
        extra_headers={"HTTP-Referer": "https://pinchbench.com", "X-Title": "PinchBench-Judge"},
    )


def _judge_via_openai(prompt: str, model: str, timeout_seconds: float) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"status": "error", "text": "", "error": "OPENAI_API_KEY not set"}
    bare_model = model.removeprefix("openai/")
    return _judge_via_openai_compat(
        prompt, bare_model,
        "https://api.openai.com/v1/chat/completions",
        api_key, timeout_seconds,
    )


def _judge_via_anthropic(prompt: str, model: str, timeout_seconds: float) -> Dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"status": "error", "text": "", "error": "ANTHROPIC_API_KEY not set"}
    bare_model = model.removeprefix("anthropic/")
    payload = json.dumps({
        "model": bare_model,
        "max_tokens": 2048,
        "temperature": 0.0,
        "system": _JUDGE_SYSTEM_MSG,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    req = request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, headers=headers, method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        logger.error("Anthropic judge API error (%s): %s", exc.code, body)
        return {"status": "error", "text": "", "error": f"HTTP {exc.code}: {body}"}
    except error.URLError as exc:
        logger.error("Anthropic judge network error: %s", exc)
        return {"status": "error", "text": "", "error": str(exc)}
    except TimeoutError:
        return {"status": "timeout", "text": "", "error": "Request timed out"}

    content = data.get("content", [])
    text = "".join(block.get("text", "") for block in content if block.get("type") == "text")
    return {"status": "success", "text": text}


def _judge_via_claude_cli(prompt: str, model: str, timeout_seconds: float) -> Dict[str, Any]:
    """Use headless Claude CLI (claude -p) as judge."""
    cmd: List[str] = ["claude", "-p"]
    # Support "claude:model-name" to pass --model
    if ":" in model:
        _, cli_model = model.split(":", 1)
        cmd.extend(["--model", cli_model])
    try:
        result = subprocess.run(
            cmd,
            input=f"{_JUDGE_SYSTEM_MSG}\n\n{prompt}",
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return {"status": "error", "text": "", "error": "claude CLI not found"}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "text": "", "error": "claude -p timed out"}
    if result.returncode != 0:
        return {"status": "error", "text": "", "error": f"claude exit {result.returncode}: {result.stderr[:300]}"}
    return {"status": "success", "text": result.stdout}
