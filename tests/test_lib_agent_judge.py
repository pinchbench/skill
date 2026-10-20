from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib_agent import call_judge_api  # noqa: E402


class _FakeResponse:
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": '{"total": 1.0}'}}]}
        ).encode("utf-8")


class KiloJudgeTests(unittest.TestCase):
    def test_call_judge_api_kilo_requires_kilo_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = call_judge_api(
                prompt="grade this",
                model="kilo/anthropic/claude-sonnet-4-5",
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["text"], "")
        self.assertEqual(result["error"], "KILO_API_KEY not set")

    def test_call_judge_api_kilo_posts_to_gateway_with_bare_model(self) -> None:
        captured_request = None

        def fake_urlopen(req, timeout):
            nonlocal captured_request
            captured_request = req
            self.assertEqual(timeout, 12.5)
            return _FakeResponse()

        with patch.dict(os.environ, {"KILO_API_KEY": "test-key"}, clear=True), patch(
            "lib_agent.request.urlopen", side_effect=fake_urlopen
        ):
            result = call_judge_api(
                prompt="grade this",
                model="kilo/anthropic/claude-sonnet-4-5",
                timeout_seconds=12.5,
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["text"], '{"total": 1.0}')
        self.assertIsNotNone(captured_request)
        self.assertEqual(
            captured_request.full_url,
            "https://api.kilo.ai/api/gateway/chat/completions",
        )
        self.assertEqual(captured_request.get_method(), "POST")
        self.assertEqual(captured_request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(captured_request.headers["Content-type"], "application/json")

        payload = json.loads(captured_request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "anthropic/claude-sonnet-4-5")
        self.assertEqual(payload["temperature"], 0.0)
        self.assertEqual(payload["max_completion_tokens"], 2048)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1], {"role": "user", "content": "grade this"})

    def test_call_judge_api_kilo_dispatch_does_not_fall_back_to_openrouter(self) -> None:
        with patch.dict(os.environ, {"KILO_API_KEY": "test-key"}, clear=True), patch(
            "lib_agent._judge_via_openai_compat",
            return_value={"status": "success", "text": "ok"},
        ) as compat:
            result = call_judge_api(
                prompt="grade this",
                model="kilo/openai/gpt-4o",
                timeout_seconds=30,
            )

        self.assertEqual(result, {"status": "success", "text": "ok"})
        compat.assert_called_once_with(
            "grade this",
            "openai/gpt-4o",
            "https://api.kilo.ai/api/gateway/chat/completions",
            "test-key",
            30,
        )


class MiniMaxJudgeTests(unittest.TestCase):
    def test_openrouter_serializes_current_and_explicit_legacy_models(self) -> None:
        for model in (
            "minimax/minimax-m3.1-flash:free", "minimax/minimax-m3",
            "minimax/minimax-m2.7", "minimax/minimax-m2.5", "minimax/minimax-m2.1",
        ):
            with self.subTest(model=model), patch.dict(
                os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=True
            ), patch("lib_agent.request.urlopen", return_value=_FakeResponse()) as urlopen:
                result = call_judge_api(prompt="grade this", model=f"openrouter/{model}")
            self.assertEqual(result["status"], "success")
            req = urlopen.call_args.args[0]
            self.assertEqual(req.full_url, "https://openrouter.ai/api/v1/chat/completions")
            self.assertEqual(req.get_method(), "POST")
            payload = json.loads(req.data)
            self.assertEqual(payload["model"], model)
            self.assertEqual(payload["messages"][1], {"role": "user", "content": "grade this"})
            for field in ("thinking", "reasoning_effort", "service_tier", "reasoning_split"):
                self.assertNotIn(field, payload)


if __name__ == "__main__":
    unittest.main()
