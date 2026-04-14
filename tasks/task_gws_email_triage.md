---
id: task_gws_email_triage
name: GWS Email Triage
category: gws
grading_type: hybrid
timeout_seconds: 300
grading_weights:
  automated: 0.5
  llm_judge: 0.5
workspace_files: []
prerequisites:
  - npm:@juppytt/fws
  - cli:gws
---

## Prompt

You have access to a Google Workspace account through the `gws` CLI tool (`gws --help` for usage).

Your inbox has several unread emails. Triage them:

1. Check your unread emails
2. Read each message to understand its content and urgency
3. For the most urgent email, draft a reply (save as draft, don't send)
4. Create a triage report saved to `triage_report.md` with priority (P0-P3), category, and recommended action for each email, sorted by priority (most urgent first)

## Expected Behavior

The agent should:

1. Discover and use gws Gmail commands to list and read emails
2. Analyze message content, sender, and urgency
3. Identify the most urgent email and create a draft reply
4. Write a structured triage report to `triage_report.md`

This tests the agent's ability to discover and use the gws CLI for a multi-step email workflow: list, read, draft, and synthesize.

## Grading Criteria

- [ ] Agent listed unread emails using gws
- [ ] Agent read individual messages using gws
- [ ] Agent created a draft reply for the most urgent email
- [ ] File `triage_report.md` created in workspace
- [ ] All unread messages are present in the report
- [ ] Each message has a priority assigned (P0-P3)
- [ ] Each message has a recommended action
- [ ] Report is sorted by priority

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    """
    Grade the GWS email triage task.
    """
    from pathlib import Path
    import re

    scores = {}
    workspace = Path(workspace_path)

    used_list = False
    used_get = False
    used_draft = False

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
        if "gws" in cmd and ("triage" in cmd or "messages list" in cmd):
            used_list = True
        if "gws" in cmd and "messages get" in cmd:
            used_get = True
        if "gws" in cmd and "drafts create" in cmd:
            used_draft = True

    scores["listed_emails"] = 1.0 if used_list else 0.0
    scores["read_messages"] = 1.0 if used_get else 0.0
    scores["created_draft"] = 1.0 if used_draft else 0.0

    report_file = workspace / "triage_report.md"
    if report_file.exists():
        scores["report_created"] = 1.0
        content = report_file.read_text().lower()

        has_priorities = bool(re.search(r'p[0-3]', content))
        scores["priorities_assigned"] = 1.0 if has_priorities else 0.0

        p0_pos = content.find("p0")
        p3_pos = content.find("p3")
        if p0_pos >= 0 and p3_pos >= 0:
            scores["sorted_by_priority"] = 1.0 if p0_pos < p3_pos else 0.0
        else:
            scores["sorted_by_priority"] = 0.5
    else:
        scores["report_created"] = 0.0
        scores["priorities_assigned"] = 0.0
        scores["sorted_by_priority"] = 0.0

    return scores
```

## LLM Judge Rubric

### Criterion 1: GWS CLI Discovery and Usage (Weight: 30%)

**Score 1.0**: Agent discovered and fluently used gws Gmail commands (list, get, drafts) with correct parameters.
**Score 0.75**: Agent used the gws CLI correctly but with minor parameter issues or extra unnecessary calls.
**Score 0.5**: Agent used some gws commands but struggled with syntax or missed key commands.
**Score 0.25**: Agent barely used gws CLI or used incorrect commands.
**Score 0.0**: Agent did not use gws CLI at all.

### Criterion 2: Triage Quality (Weight: 40%)

**Score 1.0**: All emails correctly prioritized with accurate categories and specific, actionable recommendations.
**Score 0.75**: Most emails correctly prioritized with minor misclassifications. Recommendations are reasonable.
**Score 0.5**: Some emails correctly prioritized but notable errors in judgment. Recommendations are generic.
**Score 0.25**: Priority assignments are mostly incorrect or missing.
**Score 0.0**: No meaningful triage performed.

### Criterion 3: Draft Reply Quality (Weight: 30%)

**Score 1.0**: Draft reply targets the correct urgent email with a professional response that acknowledges the situation.
**Score 0.75**: Draft targets the right email with a reasonable response, but tone or content could be improved.
**Score 0.5**: Draft created but targets a less appropriate email, or content is generic.
**Score 0.25**: Draft created but with incorrect format or irrelevant content.
**Score 0.0**: No draft created.

## Additional Notes

This task requires [fws](https://github.com/juppytt/fws) to be running as a mock GWS server. The test runner should execute `fws server start` before the task begins and set environment variables (GOOGLE_WORKSPACE_CLI_CONFIG_DIR, GOOGLE_WORKSPACE_CLI_TOKEN, HTTPS_PROXY, SSL_CERT_FILE).

The fws seed data includes 5 emails: 3 unread inbox messages (from alice@company.com about Q3 Planning, bob@company.com about a code review, notifications@github.com about a CI failure), 1 sent message, and 1 read message.
