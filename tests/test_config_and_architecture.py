import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from prospector_service.config import Settings


@pytest.mark.parametrize(
    "options",
    [
        {"engine_worker_concurrency": 2},
        {"queue_capacity": 0},
        {"callback_max_attempts": 0},
        {"platform_callback_origin": "http://platform.example.com"},
        {"platform_callback_origin": "https://user:password@platform.example.com"},
        {"platform_callback_origin": "https://platform.example.com/path"},
        {"platform_callback_origin": "https://plat\nform.example.com"},
        {"platform_callback_origin": "https://platform.example.com:invalid"},
        {"platform_callback_origin": "http://127.0.0.1:8080"},
        {"app_env": "production", "allow_local_callbacks": True},
    ],
)
def test_invalid_settings(options):
    with pytest.raises(ValidationError):
        Settings(**options)


def test_explicit_local_development_callback_and_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOW_LOCAL_CALLBACKS", "true")
    monkeypatch.setenv("PLATFORM_CALLBACK_ORIGIN", "http://127.0.0.1:9000")
    monkeypatch.setenv("ENGINE_HEADLESS", "true")
    monkeypatch.setenv("QUEUE_CAPACITY", "3")
    config = Settings.from_env()
    assert config.engine_headless and config.queue_capacity == 3
    assert config.platform_callback_origin == "http://127.0.0.1:9000"


def test_only_public_engine_imports_and_no_cli_or_database():
    import prospector_service

    root = Path(prospector_service.__file__).parent
    banned = {
        "rich",
        "bs4",
        "playwright",
        "prisma",
        "psycopg",
        "sqlalchemy",
        "scraper",
        "prospector_cli",
        "engines",
        "nest",
        "exporters",
    }
    for file in root.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                module = node.module or ""
                assert module.split(".")[0] not in banned
                if module.startswith("prospector_engine"):
                    assert module in {"prospector_engine", "prospector_engine.browser"}
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] not in banned for alias in node.names)
