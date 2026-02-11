Here's the prompt for SUBTASK 2: Benchmark Runner Implementation:

---

## Task: Implement OpenClaw Agent Execution in PinchBench

**Context**: You're building the core agent execution logic for PinchBench, a benchmarking system that evaluates LLM models as OpenClaw agents. The scaffold exists in [`benchmark.py`](benchmark.py) and [`lib_tasks.py`](lib_tasks.py). You need to implement the actual agent spawning and transcript collection.

**Goal**: Factor out and complete the [`OpenClawAgent.execute_task()`](benchmark.py:45) method to run real OpenClaw agents against benchmark tasks.

This should probably live in a library file called `lib_agent.py` or similar.

---

### Requirements

#### 1. CLI Arguments (extend `main()`)

Add argument parsing:

```
--model         Model identifier (e.g., anthropic/claude-sonnet-4) [REQUIRED]
--suite         Tasks to run: "all", "automated-only", or comma-separated IDs (default: all)
--output-dir    Results directory (default: results/)
--no-upload     Skip uploading to server
--timeout-multiplier  Scale all task timeouts (default: 1.0)
```

#### 2. Agent Setup (before task execution)

Create a test agent for the model under test:

```bash
openclaw agents add bench-{model_slug} \
  --model {model} \
  --workspace /tmp/pinchbench/{run_id}/workspace \
  --non-interactive
```

Where `model_slug` = model identifier with `/` and `.` replaced by `-` (e.g., `anthropic-claude-sonnet-4`).

Skip creation if agent already exists (check `openclaw agents list` output).

#### 3. Task Execution Loop

For each task:

**a) Create isolated workspace:**

```python
workspace = Path(f"/tmp/pinchbench/{run_id}/{task.task_id}/")
workspace.mkdir(parents=True, exist_ok=True)
```

**b) Copy workspace files from task spec:**

```python
for file_spec in task.workspace_files:
    source = skill_dir / "fixtures" / file_spec["source"]
    dest = workspace / file_spec["dest"]
    shutil.copy(source, dest)
```

**c) Execute agent via CLI:**

```bash
openclaw agent \
  --agent bench-{model_slug} \
  --session-id {task_id}_{timestamp} \
  --message "{task.prompt}"
```

Use `subprocess.run()` with:

- `timeout=task.timeout_seconds * timeout_multiplier`
- `capture_output=True`
- `text=True`
- `cwd=str(workspace)` (set working directory to isolated workspace)

**d) Handle timeout gracefully:**

```python
try:
    result = subprocess.run([...], timeout=timeout)
    timed_out = False
except subprocess.TimeoutExpired:
    timed_out = True
```

**e) Read transcript from:**

```
~/.openclaw/agents/bench-{model_slug}/sessions/{session_id}.jsonl
```

Parse as list of JSON objects (one per line).

#### 4. Return Structure

`execute_task()` should return:

```python
{
    "agent_id": str,
    "task_id": str,
    "status": "success" | "timeout" | "error",
    "transcript": list[dict],  # Parsed JSONL events
    "workspace": str,          # Path to isolated workspace
    "exit_code": int,
    "timed_out": bool,
    "execution_time": float,
    "stdout": str,
    "stderr": str,
}
```

#### 5. Aggregate Results

After all tasks complete, save to `{output_dir}/{model_slug}_{run_id}.json`:

```python
{
    "model": args.model,
    "run_id": run_id,
    "timestamp": time.time(),
    "tasks": [
        {
            "task_id": str,
            "status": str,
            "timed_out": bool,
            "execution_time": float,
            "transcript_length": int,
            "workspace": str,
        },
        ...
    ]
}
```

---

### OpenClaw Reference

From [`plans/openclaw-docs.md`](plans/openclaw-docs.md):

- **Agent creation**: `openclaw agents add <name> --model <id> --workspace <dir> --non-interactive`
- **Agent execution**: `openclaw agent --agent <id> --session-id <id> --message "<text>"`
- **Session path**: `~/.openclaw/agents/<agentId>/sessions/<sessionId>.jsonl`
- **Workspace**: Agent's cwd for file tools; relative paths resolve here

---

### Edge Cases to Handle

1. **Agent already exists**: Check `openclaw agents list` before creating
2. **Transcript file missing**: Return empty transcript, set status="error"
3. **Command not found**: Catch `FileNotFoundError` from subprocess
4. **JSON parse errors**: Log warning, include raw line in transcript
5. **Workspace cleanup**: Don't delete workspaces (needed for grading)

---

### Files to Modify

- [`benchmark.py`](benchmark.py): Main implementation
- [`lib_tasks.py`](lib_tasks.py): May need to expose `automated_checks` code extraction
- Add any other `lib_*` modules needed to keeo "benchmark.py focused on orchestration

---

### Testing

After implementation, run:

```bash
python benchmark.py --model anthropic/claude-sonnet-4 --suite task_01_calendar --no-upload
```

Verify:

- Agent created (check `openclaw agents list`)
- Workspace exists at `/tmp/pinchbench/{run_id}/task_01_calendar/`
- Transcript retrieved from `~/.openclaw/agents/bench-anthropic-claude-sonnet-4/sessions/`
- Results JSON saved to `results/`

---

This prompt gives a code-mode agent everything needed to implement the real agent execution logic while leveraging the existing scaffold and following the OpenClaw CLI patterns.
