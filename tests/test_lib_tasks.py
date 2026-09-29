"""Tests for task markdown parsing."""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib_tasks import TaskLoader  # noqa: E402


def _write_task(directory: Path, body: str) -> Path:
    path = directory / "task_sample.md"
    path.write_text(body, encoding="utf-8")
    return path


class ParseSectionsFenceTests(unittest.TestCase):
    def test_headings_inside_prompt_fence_stay_in_prompt(self) -> None:
        raw = textwrap.dedent(
            """\
            ---
            id: task_sample
            name: Sample
            category: research
            grading_type: automated
            timeout_seconds: 60
            ---

            ## Prompt

            Save the result with the format:

            ```
            # Title — {today's date}

            ## 1. {Market Question}
            **Current odds:** Yes {X}% / No {Y}%
            ```

            Only use real markets.

            ## Expected Behavior

            Write the file.

            ## Grading Criteria

            - [ ] File exists
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            task_file = _write_task(Path(tmp), raw)
            task = TaskLoader(Path(tmp)).load_task(task_file)

        self.assertIn("## 1. {Market Question}", task.prompt)
        self.assertIn("**Current odds:** Yes {X}% / No {Y}%", task.prompt)
        self.assertIn("Only use real markets.", task.prompt)
        self.assertEqual(task.expected_behavior, "Write the file.")
        self.assertEqual(task.grading_criteria, ["File exists"])

    def test_polymarket_prompt_includes_odds_template(self) -> None:
        task = TaskLoader(ROOT / "tasks").load_task(
            ROOT / "tasks" / "task_polymarket_briefing.md"
        )
        self.assertIn("**Current odds:**", task.prompt)
        self.assertIn("**Related news:**", task.prompt)
        self.assertIn("Do not fabricate markets or odds.", task.prompt)
        self.assertIn("gamma-api.polymarket.com", task.expected_behavior)


if __name__ == "__main__":
    unittest.main()
