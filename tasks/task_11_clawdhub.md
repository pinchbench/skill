---
id: task_11_clawdhub
name: Install ClawdHub Skill
category: skills
grading_type: automated
timeout_seconds: 120
workspace_files: []
---

## Prompt

Install the clawdhub skill from the OpenClaw skill registry. After installation, verify it's available by listing installed skills.

## Expected Behavior

The agent should:

1. Use the `openclaw skills install clawdhub` command to install the clawdhub skill
2. Wait for the installation to complete
3. Verify the installation by running `openclaw skills list` or checking the skills directory
4. Confirm the clawdhub skill is now available

This tests the agent's ability to use the OpenClaw CLI to manage skills and work with the skill registry.

## Grading Criteria

- [ ] Agent ran the `openclaw skills install` command
- [ ] Agent specified `clawdhub` as the skill to install
- [ ] Agent verified the installation (listed skills or checked workspace)
- [ ] Agent confirmed successful installation in response

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    """
    Grade the clawdhub installation task based on command execution.

    Args:
        transcript: Parsed JSONL transcript as list of dicts
        workspace_path: Path to the task's isolated workspace directory

    Returns:
        Dict mapping criterion names to scores (0.0 to 1.0)
    """
    import re

    scores = {
        "ran_install_command": 0.0,
        "specified_clawdhub": 0.0,
        "verified_installation": 0.0,
        "confirmed_success": 0.0,
    }

    install_command_found = False
    clawdhub_specified = False
    verified = False
    confirmed = False

    for event in transcript:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})

        # Check assistant messages for tool calls
        if msg.get("role") == "assistant":
            for item in msg.get("content", []):
                if item.get("type") == "toolCall":
                    tool_name = item.get("name", "")
                    params = item.get("params", {})

                    # Check for execute_command tool
                    if tool_name in ["execute_command", "executeCommand"]:
                        command = params.get("command", "")

                        # Check if it's an install command
                        if "openclaw" in command and "skills" in command and "install" in command:
                            install_command_found = True

                            # Check if clawdhub is specified
                            if "clawdhub" in command.lower():
                                clawdhub_specified = True

                        # Check for verification command
                        if "openclaw" in command and "skills" in command and "list" in command:
                            verified = True

                # Check text content for confirmation
                if item.get("type") == "text":
                    text = item.get("text", "").lower()
                    if any(phrase in text for phrase in [
                        "installed successfully",
                        "successfully installed",
                        "installation complete",
                        "clawdhub is now available",
                        "clawdhub has been installed",
                        "skill is installed",
                        "skill has been installed",
                    ]):
                        confirmed = True

    # Also check for verification via directory listing or file reading
    for event in transcript:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})
        if msg.get("role") == "assistant":
            for item in msg.get("content", []):
                if item.get("type") == "toolCall":
                    tool_name = item.get("name", "")
                    params = item.get("params", {})

                    # Check for list_files on skills directory
                    if tool_name in ["list_files", "listFiles"]:
                        path = params.get("path", "")
                        if "skills" in path.lower():
                            verified = True

                    # Check for read_file on skills
                    if tool_name in ["read_file", "readFile"]:
                        files = params.get("files", [])
                        if any("skill" in str(f).lower() for f in files):
                            verified = True

    scores["ran_install_command"] = 1.0 if install_command_found else 0.0
    scores["specified_clawdhub"] = 1.0 if clawdhub_specified else 0.0
    scores["verified_installation"] = 1.0 if verified else 0.0
    scores["confirmed_success"] = 1.0 if confirmed else 0.0

    return scores
```

## Additional Notes

- The clawdhub skill provides access to the OpenClaw skill registry
- Skills are installed to the workspace's `skills/` folder or the shared `~/.openclaw/skills/` directory
- The agent should handle potential errors like network issues or skill not found gracefully
- This task tests the agent's familiarity with OpenClaw's skill management system
