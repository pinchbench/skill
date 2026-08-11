from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib_agent import _custom_model_definition, ensure_agent_exists  # noqa: E402


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
            {"input": 0.6, "output": 2.4, "cacheRead": 0.12},
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


if __name__ == "__main__":
    unittest.main()
