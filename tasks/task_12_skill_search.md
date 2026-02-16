---
id: task_12_skill_search
name: Search and Install Skill from Registry
category: skills
grading_type: automated
timeout_seconds: 180
workspace_files: []
---

## Prompt

Use the skill registry to find a skill that can help with weather information, then install it. Show me the search results and confirm which skill you installed.

## Expected Behavior

The agent should:

1. Search the skill registry for weather-related skills using `openclaw skills search weather` or similar
2. Review the search results to identify an appropriate weather skill
3. Install the chosen skill using `openclaw skills install <skill-name>`
4. Confirm the installation and explain which skill was chosen and why

This tests the agent's ability to:

- Discover skills through the registry search functionality
- Evaluate options and make a selection
- Execute the installation process
- Communicate their reasoning

## Grading Criteria

- [ ] Agent searched the skill registry
- [ ] Search was related to weather/forecasting
- [ ] Agent installed a skill from search results
- [ ] Agent confirmed successful installation
- [ ] Agent explained the skill choice

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    """
    Grade the skill search and install task.

    Args:
        transcript: Parsed JSONL transcript as list of dicts
        workspace_path: Path to the task's isolated workspace directory

    Returns:
        Dict mapping criterion names to scores (0.0 to 1.0)
    """
    import re

    scores = {
        "searched_registry": 0.0,
        "weather_search": 0.0,
        "installed_skill": 0.0,
        "confirmed_installation": 0.0,
        "explained_choice": 0.0,
    }

    searched = False
    weather_query = False
    installed = False
    confirmed = False
    explained = False

    for event in transcript:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})

        if msg.get("role") == "assistant":
            for item in msg.get("content", []):
                if item.get("type") == "toolCall":
                    tool_name = item.get("name", "")
                    params = item.get("params", {})

                    if tool_name in ["execute_command", "executeCommand"]:
                        command = params.get("command", "").lower()

                        # Check for search command
                        if "openclaw" in command and "skills" in command and "search" in command:
                            searched = True
                            # Check if weather-related search
                            if any(term in command for term in ["weather", "forecast", "climate", "temperature"]):
                                weather_query = True

                        # Check for install command
                        if "openclaw" in command and "skills" in command and "install" in command:
                            installed = True

                # Check text content for confirmation and explanation
                if item.get("type") == "text":
                    text = item.get("text", "").lower()

                    # Check for installation confirmation
                    if any(phrase in text for phrase in [
                        "installed successfully",
                        "successfully installed",
                        "installation complete",
                        "has been installed",
                        "skill is now available",
                        "installed the",
                    ]):
                        confirmed = True

                    # Check for explanation of choice
                    explanation_indicators = [
                        "chose", "selected", "picked",
                        "because", "since", "as it",
                        "this skill", "provides", "offers",
                        "will help", "can help", "allows",
                        "best option", "good choice",
                    ]
                    if sum(1 for ind in explanation_indicators if ind in text) >= 2:
                        explained = True

    scores["searched_registry"] = 1.0 if searched else 0.0
    scores["weather_search"] = 1.0 if weather_query else 0.0
    scores["installed_skill"] = 1.0 if installed else 0.0
    scores["confirmed_installation"] = 1.0 if confirmed else 0.0
    scores["explained_choice"] = 1.0 if explained else 0.0

    return scores
```

## Additional Notes

- The skill registry is accessed via `openclaw skills search <query>`
- Search results include skill names, descriptions, and versions
- The agent should demonstrate decision-making when multiple options are returned
- Common weather skills might include names like "weather", "forecast", "openweather", etc.
- This task has a longer timeout (180s) to account for network latency in registry searches
