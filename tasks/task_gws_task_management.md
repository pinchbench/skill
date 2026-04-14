---
id: task_gws_task_management
name: GWS Task Management
category: gws
grading_type: hybrid
timeout_seconds: 300
grading_weights:
  automated: 0.6
  llm_judge: 0.4
workspace_files: []
prerequisites:
  - npm:@juppytt/fws
  - cli:gws
---

## Prompt

You have access to a Google Workspace account through the `gws` CLI tool (`gws --help` for usage).

Manage your tasks based on what's in your inbox:

1. Check your current task list and mark any already-completed items as done
2. Read your recent emails to find action items
3. Create a new task for each action item you find in the emails
4. Save a summary to `task_summary.md` listing what tasks you found, created, and completed

## Expected Behavior

The agent should:

1. Use gws Tasks to list current tasks and update completed ones
2. Use gws Gmail to read recent messages and extract action items
3. Create new tasks from the action items found in emails
4. Write a summary to `task_summary.md`

This tests the agent's ability to combine Tasks and Gmail, extract structured information from unstructured email content, and manage a task list.

## Grading Criteria

- [ ] Agent listed existing tasks using gws
- [ ] Agent marked completed task(s) as done
- [ ] Agent read emails using gws
- [ ] At least one new task created from email action items
- [ ] New tasks have meaningful titles derived from email content
- [ ] File `task_summary.md` created with a summary

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    """
    Grade the GWS task management task.
    """
    from pathlib import Path

    scores = {}
    workspace = Path(workspace_path)

    listed_tasks = False
    updated_task = False
    read_emails = False
    created_task = False

    def extract_commands(transcript):
        """Extract shell commands from transcript, handling multiple tool call formats."""
        cmds = []
        for event in transcript:
            if event.get("type") != "message":
                continue
            msg = event.get("message", {})
            for item in msg.get("content", []):
                t = item.get("type", "")
                if t in ("tool_use", "toolCall"):
                    cmd = (
                        item.get("input", {}).get("command", "")
                        or item.get("arguments", {}).get("command", "")
                        or item.get("params", {}).get("command", "")
                    )
                    if cmd:
                        cmds.append(cmd)
        return cmds

    for cmd in extract_commands(transcript):
        if "gws" not in cmd:
            continue
        if "tasks" in cmd and "list" in cmd:
            listed_tasks = True
        if "tasks" in cmd and ("patch" in cmd or "update" in cmd):
            updated_task = True
        if "gmail" in cmd and ("messages" in cmd or "triage" in cmd):
            read_emails = True
        if "tasks" in cmd and "insert" in cmd:
            created_task = True

    scores["listed_tasks"] = 1.0 if listed_tasks else 0.0
    scores["updated_completed"] = 1.0 if updated_task else 0.0
    scores["read_emails"] = 1.0 if read_emails else 0.0
    scores["created_new_task"] = 1.0 if created_task else 0.0

    summary_file = workspace / "task_summary.md"
    if summary_file.exists():
        scores["summary_created"] = 1.0
    else:
        scores["summary_created"] = 0.0

    return scores
```

## LLM Judge Rubric

### Criterion 1: Information Extraction (Weight: 40%)

**Score 1.0**: Agent correctly identified actionable items from emails and created well-titled, specific tasks for each.
**Score 0.75**: Agent found most action items with reasonable task titles.
**Score 0.5**: Agent found some action items but missed important ones, or task titles are vague.
**Score 0.25**: Agent created tasks but they don't clearly relate to email content.
**Score 0.0**: No tasks created from emails.

### Criterion 2: Task List Management (Weight: 30%)

**Score 1.0**: Agent correctly reviewed existing tasks, identified the completed one, marked it done, and organized new tasks logically.
**Score 0.75**: Agent managed the task list with minor oversights.
**Score 0.5**: Agent partially managed the task list but missed updating completed tasks or had other gaps.
**Score 0.25**: Agent interacted with tasks minimally.
**Score 0.0**: Agent did not manage the task list.

### Criterion 3: Summary Quality (Weight: 30%)

**Score 1.0**: Summary clearly lists what was found, what was created, and what was completed, with good organization.
**Score 0.75**: Summary covers the key points but could be better organized.
**Score 0.5**: Summary exists but is incomplete or poorly structured.
**Score 0.25**: Summary is minimal or unclear.
**Score 0.0**: No summary created.

## Additional Notes

This task requires [fws](https://github.com/juppytt/fws) to be running as a mock GWS server. The test runner should execute `fws server start` before the task begins and set environment variables (GOOGLE_WORKSPACE_CLI_CONFIG_DIR, GOOGLE_WORKSPACE_CLI_TOKEN, HTTPS_PROXY, SSL_CERT_FILE).

fws seed data includes: a "My Tasks" list with 2 tasks (1 pending: "Review Q3 proposal", 1 completed: "Update documentation"), and 5 emails with various action items (Q3 planning meeting, code review request, CI failure notification).
