---
id: task_gws_cross_service
name: GWS Cross-Service Workflow
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

You received an email from alice@company.com about a "Q3 Planning Meeting". Do the following:

1. Find and read that email to get the meeting details
2. Create a calendar event for the meeting based on what you find in the email
3. Find the "Q3 Planning Agenda" document in Drive and share it with bob@company.com (reader access)
4. Save a summary of what you did to `actions.md`

## Expected Behavior

The agent should:

1. Search or list Gmail messages to find the Q3 Planning email from Alice
2. Read the email content for meeting details
3. Use gws Calendar to create an event with the correct summary, time, and attendees
4. Use gws Drive to find the agenda document and add a permission for bob@company.com
5. Write a summary of completed actions to `actions.md`

This tests the agent's ability to coordinate across Gmail, Calendar, and Drive in a single workflow.

## Grading Criteria

- [ ] Agent found and read the Q3 Planning email
- [ ] Calendar event created with relevant summary
- [ ] Calendar event has a start time
- [ ] Q3 Planning Agenda document found in Drive
- [ ] Permission created on the document for bob@company.com
- [ ] File `actions.md` created with a summary of actions taken

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    """
    Grade the GWS cross-service workflow task.
    """
    from pathlib import Path

    scores = {}
    workspace = Path(workspace_path)

    read_email = False
    created_event = False
    found_file = False
    shared_file = False

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
        if "messages get" in cmd or "messages list" in cmd or "+triage" in cmd:
            read_email = True
        if "events insert" in cmd or "events create" in cmd:
            created_event = True
        if "files list" in cmd or "files get" in cmd:
            found_file = True
        if "permissions create" in cmd:
            shared_file = True

    scores["read_email"] = 1.0 if read_email else 0.0
    scores["created_event"] = 1.0 if created_event else 0.0
    scores["found_drive_file"] = 1.0 if found_file else 0.0
    scores["shared_file"] = 1.0 if shared_file else 0.0

    actions_file = workspace / "actions.md"
    if actions_file.exists():
        scores["actions_summary"] = 1.0
    else:
        scores["actions_summary"] = 0.0

    return scores
```

## LLM Judge Rubric

### Criterion 1: Cross-Service Coordination (Weight: 50%)

**Score 1.0**: Agent seamlessly navigated Gmail, Calendar, and Drive, extracting information from one service and using it in another. The workflow was logical and efficient.
**Score 0.75**: Agent used all three services but with minor inefficiencies or missed connections between them.
**Score 0.5**: Agent used two of three services correctly but failed to connect data between them.
**Score 0.25**: Agent attempted to use the services but struggled with most operations.
**Score 0.0**: Agent failed to use gws across multiple services.

### Criterion 2: Task Completeness (Weight: 50%)

**Score 1.0**: All four steps completed correctly: email read, event created with correct details, document shared with bob, summary written.
**Score 0.75**: Three of four steps completed correctly.
**Score 0.5**: Two of four steps completed correctly.
**Score 0.25**: One step completed correctly.
**Score 0.0**: No steps completed.

## Additional Notes

This task requires [fws](https://github.com/juppytt/fws) to be running as a mock GWS server. The test runner should execute `fws server start` before the task begins and set environment variables (GOOGLE_WORKSPACE_CLI_CONFIG_DIR, GOOGLE_WORKSPACE_CLI_TOKEN, HTTPS_PROXY, SSL_CERT_FILE).

fws seed data includes: an email from alice@company.com about "Q3 Planning Meeting", a Drive file named "Q3 Planning Agenda" (id: file001), and a primary calendar with existing events.
