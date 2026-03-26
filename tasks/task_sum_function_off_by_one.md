id: task_sum_function_off_by_one
name: Fix off-by-one error in sum function
category: coding
grading_type: automated
timeout_seconds: 120
workspace_files:
  - sum.py
  - test_sum.py

## Prompt

The workspace contains a function `sum_n(n)` in `sum.py` that is supposed to return the sum of integers from 1 to n (inclusive).

However, the implementation is incorrect and fails the provided tests.

Fix the implementation so that all tests pass.

Requirements:
- Modify only `sum.py`
- Do not change `test_sum.py`
- Do not introduce new functions
- Keep the function signature unchanged

## Expected Behavior

The function `sum_n(n)` should return:

1 + 2 + ... + n

Examples:
- sum_n(1) == 1
- sum_n(3) == 6
- sum_n(5) == 15

## Grading Criteria

- sum.py was modified
- test_sum.py was not modified
- All tests pass
- Function returns correct results for multiple inputs

## Automated Checks

def grade(transcript: list, workspace_path: str) -> dict:
    import importlib.util
    from pathlib import Path

    workspace = Path(workspace_path)
    sum_file = workspace / "sum.py"
    test_file = workspace / "test_sum.py"

    scores = {
        "sum.py was modified": 0.0,
        "test_sum.py was not modified": 0.0,
        "All tests pass": 0.0,
        "Function returns correct results for multiple inputs": 0.0,
    }

    if not sum_file.exists() or not test_file.exists():
        return scores

    original_code = sum_file.read_text()

    # Check modification via transcript heuristic
    modified = False
    for event in transcript:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})
        for item in msg.get("content", []):
            if item.get("type") == "toolCall":
                raw = str(item)
                if "sum.py" in raw and any(x in raw.lower() for x in ["write", "edit", "replace"]):
                    modified = True
    if modified:
        scores["sum.py was modified"] = 1.0

    # Ensure test file untouched
    scores["test_sum.py was not modified"] = 1.0

    # Load module dynamically
    spec = importlib.util.spec_from_file_location("sum_module", sum_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        tests = [
            module.sum_n(1) == 1,
            module.sum_n(3) == 6,
            module.sum_n(5) == 15,
            module.sum_n(10) == 55,
        ]
        if all(tests):
            scores["All tests pass"] = 1.0
            scores["Function returns correct results for multiple inputs"] = 1.0
    except Exception:
        pass

    return scores