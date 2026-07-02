---
id: task_cron_on_exit
name: Event-Driven Cron (on-exit Schedules)
category: productivity
grading_type: automated
timeout_seconds: 120
workspace_files: []
---

## Prompt

OpenClaw's cron system recently added a new event-driven `on-exit` schedule kind: instead of firing at a fixed time, it wakes the agent when a *watched command* exits. Jobs can either run inside the current/main session or be fully detached into their own session.

Convert each automation request below into a JSON array written to `cron_jobs.json`. Each array entry must be an object with exactly these fields:

- `name`: a short, descriptive slug for the job (lowercase, hyphen-separated)
- `schedule`: an object with:
  - `kind`: always the literal string `"on-exit"`
  - `command`: the exact shell command being watched, copied verbatim from the request
  - `detach`: `true` if the job must run in its own separate/detached session (i.e. it should NOT appear in or block the main conversation), or `false` if it should stay attached to the current/main session
- `prompt`: the instruction to send the agent once the watched command exits

**Automations to convert:**

1. "When the nightly backup script at `/usr/local/bin/backup.sh` finishes, check its exit code and text me a one-line summary of whether it succeeded or failed. Run this in its own detached session so it doesn't interrupt my main chat."
2. "Watch `npm run build` in the release pipeline — once it exits, post the last 20 lines of output to the #releases channel. Keep it attached to my main session since I want to see it in my current conversation."
3. "After `rsync -av /data /backup` completes, verify the backup directory isn't empty and let me know. This should run in the background and must NOT show up in my main session — run it detached."
4. "When the docker build for the API image (`docker build -t api:latest .`) exits, if it failed restart it once automatically and tell me either way. Keep it in my main session so I can follow along."

## Expected Behavior

The agent should:

1. Recognize that this describes the new `on-exit` cron schedule kind (event-driven, not time-based)
2. Produce exactly 4 JSON objects, one per automation
3. Copy the watched command verbatim into `schedule.command`
4. Correctly infer `detach: true` for automations #1 and #3 (explicitly "detached" / "not in main session")
5. Correctly infer `detach: false` for automations #2 and #4 (explicitly "attached" / "main session" / "current conversation")
6. Write a `prompt` field summarizing what the agent should do once the command exits
7. Save everything to `cron_jobs.json` as a valid JSON array

## Grading Criteria

- [ ] File `cron_jobs.json` created with valid JSON array
- [ ] Exactly 4 entries present
- [ ] Every entry has `name`, `schedule`, and `prompt` fields
- [ ] Every `schedule.kind` equals `"on-exit"`
- [ ] Backup job command matches `/usr/local/bin/backup.sh` verbatim
- [ ] Build job command matches `npm run build` verbatim
- [ ] Rsync job command matches `rsync -av /data /backup` verbatim
- [ ] Docker job command matches `docker build -t api:latest .` verbatim
- [ ] Backup job `detach` is `true`
- [ ] Build job `detach` is `false`
- [ ] Rsync job `detach` is `true`
- [ ] Docker job `detach` is `false`

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    from pathlib import Path
    import json

    scores = {
        "file_created": 0.0,
        "valid_json": 0.0,
        "entry_count": 0.0,
        "all_have_fields": 0.0,
        "all_kind_on_exit": 0.0,
        "backup_command_correct": 0.0,
        "build_command_correct": 0.0,
        "rsync_command_correct": 0.0,
        "docker_command_correct": 0.0,
        "backup_detach_correct": 0.0,
        "build_detach_correct": 0.0,
        "rsync_detach_correct": 0.0,
        "docker_detach_correct": 0.0,
    }

    workspace = Path(workspace_path)
    output_file = workspace / "cron_jobs.json"
    if not output_file.exists():
        return scores

    scores["file_created"] = 1.0

    try:
        data = json.loads(output_file.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            data = data.get("jobs", data.get("cron_jobs", []))
        scores["valid_json"] = 1.0
    except (json.JSONDecodeError, AttributeError):
        return scores

    entries = [e for e in data if isinstance(e, dict)]
    scores["entry_count"] = 1.0 if len(entries) >= 4 else (0.5 if len(entries) >= 2 else 0.0)

    fields_ok = sum(
        1 for e in entries
        if all(k in e for k in ("name", "schedule", "prompt")) and isinstance(e.get("schedule"), dict)
    )
    scores["all_have_fields"] = 1.0 if fields_ok >= 4 else (0.5 if fields_ok >= 2 else 0.0)

    schedules = [e.get("schedule", {}) for e in entries if isinstance(e.get("schedule"), dict)]
    kind_ok = sum(1 for s in schedules if str(s.get("kind", "")).strip() == "on-exit")
    scores["all_kind_on_exit"] = 1.0 if kind_ok >= 4 else (0.5 if kind_ok >= 2 else 0.0)

    def find_schedule(keyword):
        for s in schedules:
            cmd = str(s.get("command", ""))
            if keyword in cmd:
                return s
        return None

    checks = [
        ("backup.sh", "backup_command_correct", "backup_detach_correct", True),
        ("npm run build", "build_command_correct", "build_detach_correct", False),
        ("rsync", "rsync_command_correct", "rsync_detach_correct", True),
        ("docker build", "docker_command_correct", "docker_detach_correct", False),
    ]

    for keyword, cmd_key, detach_key, expected_detach in checks:
        sched = find_schedule(keyword)
        if sched is None:
            continue
        scores[cmd_key] = 1.0
        detach_val = sched.get("detach")
        if isinstance(detach_val, bool) and detach_val == expected_detach:
            scores[detach_key] = 1.0
        elif isinstance(detach_val, str) and detach_val.strip().lower() == str(expected_detach).lower():
            scores[detach_key] = 1.0

    return scores
```

## Additional Notes

- This task tests whether the agent picked up on OpenClaw's new event-driven `on-exit` cron schedule kind (as opposed to time-based `cron`/`interval` schedules) and correctly reasoned about session detachment semantics from natural-language phrasing.
- `detach: true` should correlate with phrases like "detached", "own session", "must NOT show up in my main session".
- `detach: false` should correlate with phrases like "attached to my main session", "current conversation", "keep it in my main session".
- The exact command string must be preserved verbatim since it is what OpenClaw actually watches for exit.
