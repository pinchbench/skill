---
id: task_sanity
name: Sanity Check
category: basic
grading_type: automated
timeout_seconds: 60
workspace_files: []
---

## Prompt

Say "Hello, I'm ready!" to confirm you can respond.

## Expected Behavior

The agent should:

1. Respond with a greeting or confirmation message
2. Show that it can process and respond to simple instructions

This is a basic sanity check to ensure the benchmarking system is working correctly.

## Grading Criteria

- [ ] Agent responded successfully (any response counts)

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    """
    Grade the sanity check task - just verify the agent responded.

    Args:
        transcript: Parsed JSONL transcript as list of dicts (OpenClaw trajectory format)
        workspace_path: Path to the task's isolated workspace directory

    Returns:
        Dict mapping criterion names to scores (0.0 to 1.0)
    """
    scores = {}
    
    # Check if there's any assistant response in the transcript
    has_response = False
    for entry in transcript:
        # OpenClaw trajectory format: model.completed with assistantTexts
        if entry.get("type") == "model.completed":
            data = entry.get("data", {})
            texts = data.get("assistantTexts", [])
            if texts and any(t.strip() for t in texts):
                has_response = True
                break
        # Also check trace.artifacts which contains the final assistantTexts
        if entry.get("type") == "trace.artifacts":
            data = entry.get("data", {})
            texts = data.get("assistantTexts", [])
            if texts and any(t.strip() for t in texts):
                has_response = True
                break
    
    scores["agent_responded"] = 1.0 if has_response else 0.0
    
    return scores
```
