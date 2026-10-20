from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib_agent import (  # noqa: E402
    _custom_model_definition,
    ensure_agent_exists,
    execute_openclaw_task,
    validate_openrouter_model,
)
from lib_tasks import Task  # noqa: E402


class CustomModelDefinitionTests(unittest.TestCase):
    def test_minimax_m3_uses_global_endpoint_metadata(self) -> None:
        definition = _custom_model_definition(
            "MiniMax-M3",
            "https://api.minimax.io/v1",
        )

        self.assertEqual(definition["contextWindow"], 1_000_000)
        self.assertEqual(definition["input"], ["text", "image", "video"])
        self.assertTrue(definition["reasoning"])
        self.assertEqual(
            definition["cost"],
            {"input": 0.3, "output": 1.2, "cacheRead": 0.06},
        )

    def test_minimax_m27_uses_china_endpoint_metadata(self) -> None:
        definition = _custom_model_definition(
            "MiniMax-M2.7",
            "https://api.minimaxi.com/v1/",
        )

        self.assertEqual(definition["contextWindow"], 204_800)
        self.assertEqual(definition["input"], ["text"])
        self.assertTrue(definition["reasoning"])
        self.assertEqual(
            definition["cost"],
            {
                "input": 0.3,
                "output": 1.2,
                "cacheRead": 0.06,
                "cacheWrite": 0.375,
            },
        )

    def test_unknown_endpoint_keeps_generic_defaults(self) -> None:
        definition = _custom_model_definition(
            "MiniMax-M3",
            "https://example.com/v1",
        )

        self.assertEqual(
            definition,
            {
                "id": "MiniMax-M3",
                "name": "MiniMax-M3",
                "reasoning": False,
                "input": ["text"],
                "contextWindow": 200_000,
                "maxTokens": 8192,
            },
        )

    def test_ensure_agent_writes_minimax_metadata(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_dir = root / "agents" / "bench-minimax-m3"
            workspace = root / "workspace"

            with patch("lib_agent.subprocess.run", return_value=completed), patch(
                "lib_agent._get_agent_store_dir",
                return_value=store_dir,
            ), patch("lib_agent.Path.home", return_value=root):
                created = ensure_agent_exists(
                    "bench-minimax-m3",
                    "MiniMax-M3",
                    workspace,
                    base_url="https://api.minimax.io/v1",
                    api_key="test-key",
                )

            self.assertTrue(created)
            config = json.loads((store_dir / "agent" / "models.json").read_text("utf-8"))
            model = config["models"]["providers"]["custom"]["models"][0]
            self.assertEqual(
                model,
                _custom_model_definition("MiniMax-M3", "https://api.minimax.io/v1"),
            )


class MiniMaxBoundaryTests(unittest.TestCase):
    def test_registry_lists_only_current_minimax_models_flash_first(self) -> None:
        models = yaml.safe_load((ROOT / ".github/benchmark-models.yml").read_text())["models"]
        self.assertEqual(len(models), len(set(models)))
        self.assertEqual(
            [model for model in models if model.startswith("openrouter/minimax/")],
            ["openrouter/minimax/minimax-m3.1-flash:free", "openrouter/minimax/minimax-m3"],
        )

    def test_flash_metadata_and_regional_costs_in_serialized_agent_config(self) -> None:
        for endpoint in (
            "https://api.minimax.io/v1",
            "https://api.minimax.cn/v1/",
            "https://api.minimaxi.com/v1/",
        ):
            for model_id in ("MiniMax-M3.1-Flash", "MiniMax-M3"):
                with self.subTest(endpoint=endpoint, model=model_id), TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    completed = subprocess.CompletedProcess([], 0, "", "")
                    with patch("lib_agent.Path.home", return_value=root), patch(
                        "lib_agent.subprocess.run", return_value=completed
                    ) as run:
                        self.assertTrue(ensure_agent_exists(
                            "bench-test", model_id, root / "workspace", base_url=endpoint
                        ))
                    add_cmd = run.call_args_list[-1].args[0]
                    self.assertEqual(add_cmd[add_cmd.index("--model") + 1], model_id)
                    config = json.loads((
                        root / ".openclaw/agents/bench-test/agent/models.json"
                    ).read_text())
                    provider = config["models"]["providers"]["custom"]
                    self.assertEqual(provider["baseUrl"], endpoint)
                    self.assertEqual(provider["apiKey"], "${OPENAI_API_KEY}")
                    self.assertEqual(provider["api"], "openai-completions")
                    self.assertEqual(config["defaultModel"], model_id)
                    model = provider["models"][0]
                    self.assertEqual(model["id"], model_id)
                    self.assertEqual(model["contextWindow"], 1_000_000)
                    self.assertEqual(model["input"], ["text", "image", "video"])
                    self.assertTrue(model["reasoning"])
                    if model_id == "MiniMax-M3.1-Flash":
                        self.assertEqual(model["maxTokens"], 524_288)
                        if endpoint == "https://api.minimax.io/v1":
                            self.assertEqual(model["cost"], {
                                "input": 0.15, "output": 0.6, "cacheRead": 0.015,
                            })
                    if endpoint != "https://api.minimax.io/v1":
                        self.assertNotIn("cost", model)

    def test_gateway_and_explicit_legacy_ids_reach_agent_unchanged(self) -> None:
        for model_id in (
            "openrouter/minimax/minimax-m3.1-flash:free",
            "openrouter/minimax/minimax-m3",
            "openrouter/minimax/minimax-m2.7",
            "openrouter/minimax/minimax-m2.5",
            "openrouter/minimax/minimax-m2.1",
            "custom/saved-model",
        ):
            with self.subTest(model=model_id), TemporaryDirectory() as tmp:
                root = Path(tmp)
                main_models = root / ".openclaw/agents/main/agent/models.json"
                main_models.parent.mkdir(parents=True)
                saved = {"models": {"providers": {"custom": {"models": [{"id": "saved"}]}}}}
                main_models.write_text(json.dumps(saved))
                completed = subprocess.CompletedProcess([], 0, "", "")
                with patch("lib_agent.Path.home", return_value=root), patch(
                    "lib_agent.subprocess.run", return_value=completed
                ) as run:
                    ensure_agent_exists("bench-test", model_id, root / "workspace")
                cmd = run.call_args_list[-1].args[0]
                self.assertEqual(cmd[cmd.index("--model") + 1], model_id)
                config = json.loads((
                    root / ".openclaw/agents/bench-test/agent/models.json"
                ).read_text())
                self.assertEqual(config["defaultProvider"], model_id.split("/", 1)[0])
                self.assertEqual(config["defaultModel"], model_id.split("/", 1)[1])
                self.assertEqual(config["models"], saved["models"])
                self.assertEqual(json.loads(main_models.read_text()), saved)

    def test_explicit_legacy_custom_models_keep_their_ids(self) -> None:
        for model_id in ("MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M2.1"):
            with self.subTest(model=model_id), TemporaryDirectory() as tmp:
                root = Path(tmp)
                with patch("lib_agent.Path.home", return_value=root), patch(
                    "lib_agent.subprocess.run", return_value=subprocess.CompletedProcess(
                        [], 0, "", ""
                    )
                ) as run:
                    ensure_agent_exists(
                        "bench-test", model_id, root / "workspace",
                        base_url="https://api.minimax.io/v1",
                    )
                config = json.loads((
                    root / ".openclaw/agents/bench-test/agent/models.json"
                ).read_text())
                self.assertEqual(config["defaultModel"], model_id)
                self.assertEqual(config["models"]["providers"]["custom"]["models"][0]["id"],
                                 model_id)
                cmd = run.call_args_list[-1].args[0]
                self.assertEqual(cmd[cmd.index("--model") + 1], model_id)

    def test_existing_agent_keeps_saved_configuration_and_history(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            store = root / ".openclaw/agents/bench-test"
            config = store / "agent/models.json"
            history = store / "sessions/sessions.json"
            config.parent.mkdir(parents=True)
            history.parent.mkdir(parents=True)
            config.write_text('{"defaultModel": "MiniMax-M2.5"}')
            history.write_text('{"saved": "session"}')
            with patch("lib_agent.Path.home", return_value=root), patch(
                "lib_agent._get_agent_workspace", return_value=workspace
            ), patch("lib_agent.subprocess.run", return_value=subprocess.CompletedProcess(
                [], 0, "- bench-test\n", ""
            )) as run:
                self.assertFalse(ensure_agent_exists(
                    "bench-test", "MiniMax-M3.1-Flash", workspace,
                    base_url="https://api.minimax.io/v1",
                ))
            self.assertEqual(run.call_count, 1)
            self.assertEqual(json.loads(config.read_text()), {"defaultModel": "MiniMax-M2.5"})
            self.assertEqual(json.loads(history.read_text()), {"saved": "session"})

    def test_unknown_custom_model_and_endpoint_keep_generic_metadata(self) -> None:
        for model_id, endpoint in (
            ("my-saved-model", "https://api.minimax.io/v1"),
            ("MiniMax-M3.1-Flash", "https://example.com/v1"),
            ("MiniMax-M3.1-Flash", "https://api.minimax.io.example.com/v1"),
        ):
            with self.subTest(model=model_id, endpoint=endpoint):
                self.assertEqual(_custom_model_definition(model_id, endpoint), {
                    "id": model_id, "name": model_id, "reasoning": False,
                    "input": ["text"], "contextWindow": 200_000, "maxTokens": 8192,
                })

    def test_flash_catalog_validation_preserves_free_suffix(self) -> None:
        import os
        from unittest.mock import MagicMock

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=True), patch(
            "lib_agent.request.urlopen", return_value=MagicMock()
        ) as urlopen:
            self.assertTrue(validate_openrouter_model(
                "openrouter/minimax/minimax-m3.1-flash:free"
            ))
        req = urlopen.call_args.args[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.full_url,
                         "https://openrouter.ai/api/v1/models/minimax%2Fminimax-m3.1-flash:free")

    def test_task_handoff_preserves_prompt_thinking_and_transcript(self) -> None:
        transcript = [{"type": "message", "message": {
            "role": "assistant", "content": "answer", "reasoning_content": "reasoning",
            "tool_calls": [{"id": "call_1", "type": "function"}],
        }}]
        for thinking in (None, "low", "medium", "high", "xhigh", "adaptive"):
            for multi in (False, True):
                with self.subTest(thinking=thinking, multi=multi), TemporaryDirectory() as tmp:
                    workspace = Path(tmp)
                    prompt = "Inspect image.png and clip.mp4\nPreserve the observations."
                    task = Task(
                        "test", "Test", "test", "automated", 30, [], prompt, "", [],
                        frontmatter={"sessions": [prompt]} if multi else {},
                    )
                    with patch("lib_agent.cleanup_agent_sessions"), patch(
                        "lib_agent.prepare_task_workspace", return_value=workspace
                    ), patch("lib_agent._load_transcript", return_value=(transcript, None)), patch(
                        "lib_agent.subprocess.run",
                        return_value=subprocess.CompletedProcess([], 0, "", ""),
                    ) as run:
                        result = execute_openclaw_task(
                            task=task, agent_id="bench-flash", model_id="MiniMax-M3.1-Flash",
                            run_id="test", timeout_multiplier=1, skill_dir=ROOT,
                            thinking_level=thinking,
                        )
                    cmd = run.call_args.args[0]
                    self.assertEqual(cmd[:4], ["openclaw", "agent", "--agent", "bench-flash"])
                    self.assertEqual(cmd[cmd.index("--message") + 1], prompt)
                    if thinking:
                        self.assertEqual(cmd[cmd.index("--thinking") + 1], thinking)
                    else:
                        self.assertNotIn("--thinking", cmd)
                    self.assertEqual(result["status"], "success")
                    self.assertEqual(result["transcript"], transcript)


if __name__ == "__main__":
    unittest.main()
