from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace_os.model_provider import (
    ModelMessage,
    ModelProfile,
    ModelRequest,
    ModelRouter,
    ModelRoutingConfig,
    NoModelProvider,
    OpenAICompatibleProvider,
    build_model_router,
    load_modeling_config,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class ModelProviderTests(unittest.TestCase):
    def test_no_model_provider_returns_deterministic_fallback(self):
        provider = NoModelProvider()
        request_payload = ModelRequest(
            task_type="planning",
            messages=(ModelMessage(role="user", content="Plan the next cycle."),),
        )

        result = provider.generate(request_payload)

        self.assertTrue(provider.is_available())
        self.assertEqual("none", result.provider)
        self.assertTrue(result.used_fallback)
        self.assertIn("No external model configured", result.content)
        self.assertIn("task_type=planning", result.content)

    def test_model_router_falls_back_when_preferred_provider_is_missing(self):
        config = ModelRoutingConfig(
            enabled=True,
            default_profile="remote",
            fallback_profile="none",
            routes={"planning": ("remote",)},
            profiles={
                "remote": ModelProfile(
                    name="remote",
                    kind="openai_compatible",
                    enabled=True,
                    base_url=None,
                    model=None,
                )
            },
        )
        router = ModelRouter(config)
        request_payload = ModelRequest.from_prompt("Plan the cycle.", task_type="planning")

        result = router.generate(request_payload)

        self.assertEqual("none", result.provider)
        self.assertTrue(result.used_fallback)
        self.assertIn("remote", result.candidate_chain)
        self.assertIn("none", result.candidate_chain)

    def test_load_modeling_config_resolves_env_backed_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "workspace.json"
            config_path.write_text(
                json.dumps(
                    {
                        "modeling": {
                            "enabled": True,
                            "default_profile": "remote_reasoner",
                            "fallback_profile": "none",
                            "routes": {"planning": ["remote_reasoner"]},
                            "profiles": {
                                "remote_reasoner": {
                                    "kind": "openai_compatible",
                                    "enabled": True,
                                    "base_url_env": "TEST_MODEL_BASE_URL",
                                    "api_key_env": "TEST_MODEL_API_KEY",
                                    "model_env": "TEST_MODEL_NAME",
                                }
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "TEST_MODEL_BASE_URL": "https://example.invalid/v1",
                    "TEST_MODEL_API_KEY": "secret",
                    "TEST_MODEL_NAME": "test-model",
                },
                clear=False,
            ):
                config = load_modeling_config(config_path)

        self.assertTrue(config.enabled)
        self.assertEqual("remote_reasoner", config.default_profile)
        self.assertIn("planning", config.routes)
        self.assertEqual("https://example.invalid/v1", config.profiles["remote_reasoner"].base_url)
        self.assertEqual("test-model", config.profiles["remote_reasoner"].model)
        self.assertEqual("secret", config.profiles["remote_reasoner"].api_key)

    def test_openai_compatible_provider_posts_chat_completion_request(self):
        provider = OpenAICompatibleProvider(
            name="remote_reasoner",
            base_url="https://api.example.invalid/v1",
            model="test-model",
            api_key="secret-token",
        )
        request_payload = ModelRequest.from_prompt("Summarize the cycle.", task_type="review")

        with patch("workspace_os.model_provider.request.urlopen", return_value=_FakeHTTPResponse({"choices": [{"message": {"content": "summary"}}]})) as mocked:
            result = provider.generate(request_payload)

        http_request = mocked.call_args.args[0]
        body = json.loads(http_request.data.decode("utf-8"))

        self.assertEqual("remote_reasoner", result.provider)
        self.assertEqual("test-model", result.model)
        self.assertEqual("summary", result.content)
        self.assertEqual("https://api.example.invalid/v1/chat/completions", http_request.full_url)
        self.assertEqual("Bearer secret-token", http_request.get_header("Authorization"))
        self.assertEqual("test-model", body["model"])
        self.assertEqual("review", request_payload.task_type)

    def test_build_model_router_defaults_to_no_model_when_unconfigured(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "workspace.json"
            config_path.write_text("{}", encoding="utf-8")

            router = build_model_router(config_path)
            result = router.generate(ModelRequest.from_prompt("Do the task.", task_type="planning"))

        self.assertEqual("none", result.provider)
        self.assertTrue(result.used_fallback)
        self.assertIn("no external model configured", result.fallback_reason or "")

    def test_disabled_modeling_ignores_environment_providers(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "workspace.json"
            config_path.write_text(
                json.dumps(
                    {
                        "modeling": {
                            "enabled": False,
                            "default_profile": "remote_reasoner",
                            "fallback_profile": "none",
                            "profiles": {
                                "remote_reasoner": {
                                    "kind": "openai_compatible",
                                    "enabled": True,
                                    "base_url_env": "TEST_DISABLED_MODEL_BASE_URL",
                                    "api_key_env": "TEST_DISABLED_MODEL_API_KEY",
                                    "model_env": "TEST_DISABLED_MODEL_NAME",
                                }
                            },
                            "routes": {"planning": ["remote_reasoner"]},
                        }
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "TEST_DISABLED_MODEL_BASE_URL": "https://example.invalid/v1",
                    "TEST_DISABLED_MODEL_API_KEY": "secret",
                    "TEST_DISABLED_MODEL_NAME": "test-model",
                },
                clear=False,
            ):
                router = build_model_router(config_path)
                result = router.generate(ModelRequest.from_prompt("Plan the cycle.", task_type="planning"))

        self.assertEqual("none", result.provider)
        self.assertTrue(result.used_fallback)
        self.assertEqual(("none",), result.candidate_chain)


if __name__ == "__main__":
    unittest.main()
