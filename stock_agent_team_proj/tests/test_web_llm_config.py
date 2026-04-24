import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestWebAnalyzeLLMConfig(unittest.TestCase):
    def test_analyze_uses_config_loader_for_api_key(self):
        fake_loader = SimpleNamespace(
            default_provider="openai_compatible",
            get_provider=lambda: SimpleNamespace(
                api_key="resolved-from-loader",
                base_url="https://example.com/v1",
                model="test-model",
                temperature=0.25,
                max_tokens=512,
            ),
        )

        with patch("config.config_loader.get_llm_config", return_value=fake_loader):
            from web.api.analyze import get_llm_config

            config = get_llm_config()

        self.assertEqual(config["provider"], "openai_compatible")
        self.assertEqual(config["api_key"], "resolved-from-loader")
        self.assertEqual(config["base_url"], "https://example.com/v1")
        self.assertEqual(config["model"], "test-model")
        self.assertEqual(config["temperature"], 0.25)
        self.assertEqual(config["max_tokens"], 512)

    def test_openai_compatible_env_overrides_base_url_and_model(self):
        fake_loader = SimpleNamespace(
            default_provider="openai_compatible",
            get_provider=lambda: SimpleNamespace(
                api_key="resolved-from-loader",
                base_url="https://from-yaml.com/v1",
                model="from-yaml-model",
                temperature=0.25,
                max_tokens=512,
            ),
        )

        with patch("config.config_loader.get_llm_config", return_value=fake_loader):
            from web.api.analyze import get_llm_config

            with patch.dict(
                os.environ,
                {
                    "OPENAI_BASE_URL": "https://from-env.com/v1",
                    "OPENAI_MODEL": "from-env-model",
                },
            ):
                config = get_llm_config()

        self.assertEqual(config["base_url"], "https://from-env.com/v1")
        self.assertEqual(config["model"], "from-env-model")
        self.assertEqual(config["api_key"], "resolved-from-loader")

    def test_non_openai_provider_ignores_openai_env_urls(self):
        fake_loader = SimpleNamespace(
            default_provider="qwen",
            get_provider=lambda: SimpleNamespace(
                api_key="qwen-key",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model="qwen-plus",
                temperature=0.2,
                max_tokens=100,
            ),
        )

        with patch("config.config_loader.get_llm_config", return_value=fake_loader):
            from web.api.analyze import get_llm_config

            with patch.dict(
                os.environ,
                {"OPENAI_BASE_URL": "https://should-not-apply.com/v1"},
            ):
                config = get_llm_config()

        self.assertEqual(config["base_url"], "https://dashscope.aliyuncs.com/compatible-mode/v1")


class TestWebAppDotenvLoading(unittest.TestCase):
    def test_web_app_loads_dotenv_on_import(self):
        sys.modules.pop("web.app", None)
        fake_dotenv = SimpleNamespace(load_dotenv=Mock())

        with patch.dict(sys.modules, {"dotenv": fake_dotenv}):
            import web.app

            importlib.reload(web.app)

        self.assertGreaterEqual(fake_dotenv.load_dotenv.call_count, 1)

    def test_web_app_imports_without_python_dotenv(self):
        sys.modules.pop("web.app", None)
        sys.modules.pop("dotenv", None)

        import web.app

        importlib.reload(web.app)

    def test_web_app_fallback_loads_env_file_without_python_dotenv(self):
        sys.modules.pop("web.app", None)
        sys.modules.pop("dotenv", None)

        import web.app

        importlib.reload(web.app)

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "TEST_PROJECT_ENV_KEY=test-key\nTEST_PROJECT_ENV_URL=https://example.com/v1\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                loaded = web.app.load_project_env(env_path)
                self.assertTrue(loaded)
                self.assertEqual(os.environ["TEST_PROJECT_ENV_KEY"], "test-key")
                self.assertEqual(os.environ["TEST_PROJECT_ENV_URL"], "https://example.com/v1")
