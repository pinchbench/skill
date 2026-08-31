from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib_grading import _extract_grading_code
from lib_tasks import TaskLoader


def _load_grader(task_name: str) -> dict:
    task = TaskLoader(ROOT / "tasks").load_task(ROOT / "tasks" / task_name)
    namespace: dict = {}
    exec(_extract_grading_code(task), namespace)  # noqa: S102
    return namespace


class ShellSelectionTests(unittest.TestCase):
    def test_selects_powershell_on_windows(self) -> None:
        locations = {"pwsh": r"C:\Program Files\PowerShell\7\pwsh.exe"}

        for task_name in (
            "task_shell_command_generator.md",
            "task_git_rescue_recovery.md",
        ):
            with self.subTest(task=task_name):
                shell_argv = _load_grader(task_name)["_shell_argv"]
                argv = shell_argv("Get-ChildItem", platform="nt", which=locations.get)

                self.assertEqual(
                    argv,
                    [
                        locations["pwsh"],
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "Get-ChildItem",
                    ],
                )

    def test_selects_bash_on_posix(self) -> None:
        for task_name in (
            "task_shell_command_generator.md",
            "task_git_rescue_recovery.md",
        ):
            with self.subTest(task=task_name):
                shell_argv = _load_grader(task_name)["_shell_argv"]
                argv = shell_argv(
                    "find .",
                    platform="posix",
                    which=lambda name: f"/bin/{name}",
                )

                self.assertEqual(argv, ["/bin/bash", "-c", "find ."])

    def test_missing_shell_is_an_infrastructure_error(self) -> None:
        for task_name in (
            "task_shell_command_generator.md",
            "task_git_rescue_recovery.md",
        ):
            with self.subTest(task=task_name):
                shell_argv = _load_grader(task_name)["_shell_argv"]
                with self.assertRaises(RuntimeError):
                    shell_argv("echo test", platform="nt", which=lambda _name: None)


class ShellCommandGeneratorGraderTests(unittest.TestCase):
    def test_normalizes_relative_and_absolute_windows_paths(self) -> None:
        normalize = _load_grader("task_shell_command_generator.md")[
            "_normalize_output_path"
        ]
        root = r"c:\fixture"

        self.assertEqual(normalize(r".\app\runtime.log", root), "app/runtime.log")
        self.assertEqual(
            normalize(r"C:\Fixture\nested\deeper\events.log", root),
            "nested/deeper/events.log",
        )
        self.assertEqual(
            normalize("/tmp/fixture/server.log", "/tmp/fixture"),
            "server.log",
        )

    def test_grades_valid_command_by_behavior(self) -> None:
        grader = _load_grader("task_shell_command_generator.md")
        if os.name == "nt":
            command = (
                "Get-ChildItem -Recurse -File -Filter *.log | "
                "Select-String -SimpleMatch -CaseSensitive 'FATAL:' | "
                "ForEach-Object { $_.Path } | Sort-Object -Unique"
            )
        else:
            command = "grep -rl --include='*.log' 'FATAL:' ."

        with TemporaryDirectory() as workspace:
            Path(workspace, "command.txt").write_text(command, encoding="utf-8")
            scores = grader["grade"]([], workspace)

        self.assertTrue(all(score == 1.0 for score in scores.values()), scores)

    def test_rejects_invalid_command(self) -> None:
        grader = _load_grader("task_shell_command_generator.md")

        with TemporaryDirectory() as workspace:
            Path(workspace, "command.txt").write_text(
                "pinchbench-command-that-does-not-exist",
                encoding="utf-8",
            )
            scores = grader["grade"]([], workspace)

        self.assertEqual(scores["executes_successfully"], 0.0)
        self.assertEqual(scores["outputs_correct_matches"], 0.0)

    def test_propagates_missing_shell_infrastructure(self) -> None:
        grader = _load_grader("task_shell_command_generator.md")

        with TemporaryDirectory() as workspace:
            Path(workspace, "command.txt").write_text("echo test", encoding="utf-8")
            with patch.dict(
                grader,
                {"_shell_argv": lambda _command: (_ for _ in ()).throw(RuntimeError())},
            ), self.assertRaises(RuntimeError):
                grader["grade"]([], workspace)


class GitRescueGraderTests(unittest.TestCase):
    def test_grades_valid_recovery_by_behavior(self) -> None:
        grader = _load_grader("task_git_rescue_recovery.md")

        with TemporaryDirectory() as workspace:
            Path(workspace, "recovery.sh").write_text(
                "git branch feature/login-fix\n"
                "git reset --hard HEAD~2\n",
                encoding="utf-8",
            )
            scores = grader["grade"]([], workspace)

        self.assertTrue(all(score == 1.0 for score in scores.values()), scores)

    def test_rejects_invalid_git_command(self) -> None:
        grader = _load_grader("task_git_rescue_recovery.md")

        with TemporaryDirectory() as workspace:
            Path(workspace, "recovery.sh").write_text(
                "git pinchbench-command-that-does-not-exist\n",
                encoding="utf-8",
            )
            scores = grader["grade"]([], workspace)

        self.assertEqual(scores["executes_successfully"], 0.0)
        self.assertEqual(scores["feature_branch_created"], 0.0)

    def test_propagates_missing_shell_infrastructure(self) -> None:
        grader = _load_grader("task_git_rescue_recovery.md")

        with TemporaryDirectory() as workspace:
            Path(workspace, "recovery.sh").write_text(
                "git status\n",
                encoding="utf-8",
            )
            with patch.dict(
                grader,
                {"_shell_argv": lambda _command: (_ for _ in ()).throw(RuntimeError())},
            ), self.assertRaises(RuntimeError):
                grader["grade"]([], workspace)


if __name__ == "__main__":
    unittest.main()
