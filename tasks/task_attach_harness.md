---
id: task_attach_harness
name: External Harness Attach Commands
category: coding
grading_type: automated
timeout_seconds: 90
workspace_files: []
---

## Prompt

OpenClaw recently added `openclaw attach`, a CLI command that binds an external coding harness (like Codex, Claude, or Aider) to an already-running Gateway session, so interactive work can be resumed without losing session state. Its syntax is:

```
openclaw attach --session <SESSION_ID> --harness <HARNESS_NAME> [--cwd <PATH>] [--detach-on-exit]
```

Where:

- `--session` is required and takes the session ID to attach to.
- `--harness` is required and takes the harness name (e.g. `codex`, `claude`, `aider`).
- `--cwd` is optional; include it **only** when a working directory is explicitly mentioned in the request.
- `--detach-on-exit` is an optional flag (it takes no value) to include **only** when the request explicitly says the harness should not keep holding onto the gateway session once it exits.

Write the exact command for each request below to `commands.txt`, one command per line, in the same order as the requests (no extra commentary, no code fences):

1. "Attach the codex harness to session abc123."
2. "I want to resume my work in session build-77 using the aider harness, rooted at /home/dev/project, and once aider exits I don't want it holding onto the session anymore."
3. "Bind claude to session s-9f2e in my current directory ~/repo."
4. "Start codex on session nightly-run-42 without any special working directory or detach behavior."

## Expected Behavior

The agent should produce four `openclaw attach` invocations that:

1. Always include `--session` and `--harness` with the correct values
2. Include `--cwd <path>` only for requests #2 and #3, using the exact path mentioned
3. Include the bare `--detach-on-exit` flag only for request #2
4. Omit `--cwd` and `--detach-on-exit` for requests #1 and #4

## Grading Criteria

- [ ] File `commands.txt` created with 4 non-empty lines
- [ ] Line 1: session `abc123`, harness `codex`, no `--cwd`, no `--detach-on-exit`
- [ ] Line 2: session `build-77`, harness `aider`, `--cwd /home/dev/project`, includes `--detach-on-exit`
- [ ] Line 3: session `s-9f2e`, harness `claude`, `--cwd ~/repo`, no `--detach-on-exit`
- [ ] Line 4: session `nightly-run-42`, harness `codex`, no `--cwd`, no `--detach-on-exit`
- [ ] Every line begins with `openclaw attach`

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    from pathlib import Path
    import re
    import shlex

    scores = {
        "file_created": 0.0,
        "four_lines": 0.0,
        "line1_correct": 0.0,
        "line2_correct": 0.0,
        "line3_correct": 0.0,
        "line4_correct": 0.0,
        "all_start_with_openclaw_attach": 0.0,
    }

    workspace = Path(workspace_path)
    output_file = workspace / "commands.txt"
    if not output_file.exists():
        return scores

    scores["file_created"] = 1.0

    raw_lines = [l.strip() for l in output_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(raw_lines) >= 4:
        scores["four_lines"] = 1.0
    lines = raw_lines[:4]

    def parse(line):
        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = line.split()
        info = {"session": None, "harness": None, "cwd": None, "detach": False, "raw": line}
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok == "--session" and i + 1 < len(tokens):
                info["session"] = tokens[i + 1]
                i += 2
                continue
            if tok == "--harness" and i + 1 < len(tokens):
                info["harness"] = tokens[i + 1]
                i += 2
                continue
            if tok == "--cwd" and i + 1 < len(tokens):
                info["cwd"] = tokens[i + 1]
                i += 2
                continue
            if tok == "--detach-on-exit":
                info["detach"] = True
                i += 1
                continue
            i += 1
        return info

    starts_ok = 0
    for line in lines:
        if line.startswith("openclaw attach"):
            starts_ok += 1
    scores["all_start_with_openclaw_attach"] = 1.0 if starts_ok == len(lines) and len(lines) >= 4 else 0.0

    if len(lines) >= 1:
        p = parse(lines[0])
        if p["session"] == "abc123" and p["harness"] == "codex" and not p["cwd"] and not p["detach"]:
            scores["line1_correct"] = 1.0

    if len(lines) >= 2:
        p = parse(lines[1])
        cwd_ok = p["cwd"] is not None and p["cwd"].rstrip("/") == "/home/dev/project"
        if p["session"] == "build-77" and p["harness"] == "aider" and cwd_ok and p["detach"]:
            scores["line2_correct"] = 1.0

    if len(lines) >= 3:
        p = parse(lines[2])
        cwd_ok = p["cwd"] is not None and p["cwd"].rstrip("/") in ("~/repo", "$HOME/repo")
        if p["session"] == "s-9f2e" and p["harness"] == "claude" and cwd_ok and not p["detach"]:
            scores["line3_correct"] = 1.0

    if len(lines) >= 4:
        p = parse(lines[3])
        if p["session"] == "nightly-run-42" and p["harness"] == "codex" and not p["cwd"] and not p["detach"]:
            scores["line4_correct"] = 1.0

    return scores
```

## Additional Notes

- This task exercises precise flag-by-flag translation of natural language into a new CLI surface (`openclaw attach`), testing whether the agent applies conditional flag logic correctly rather than always including every flag.
- Flag order within a line does not matter; the grader parses tokens rather than doing exact string matching.
- Request #2 is the only one requiring both `--cwd` and `--detach-on-exit` together, testing that the agent can combine multiple conditions correctly.
