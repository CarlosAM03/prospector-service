import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from prospector_service.config import Settings


@pytest.mark.parametrize(
    "options",
    [
        {"internal_api_key": "short"},
        {"assertion_key": "a" * 32, "internal_api_key": "a" * 32},
        {"platform_callback_origin": "https://platform.example/path"},
        {"platform_callback_origin": "https://u:p@example.com"},
        {"platform_callback_origin": "http://platform.example"},
        {"platform_callback_origin": "https://platform.example:invalid"},
        {"app_env": "production", "allow_local_callbacks": True},
        {"app_env": "production", "prospector_chromium_sandbox": "0"},
        {"max_active_batches": 0},
        {"max_active_batches": 26},
        {"prospector_chromium_sandbox": "1", "engine_browser": "msedge"},
    ],
)
def test_invalid_settings(options):
    with pytest.raises(ValidationError):
        Settings(**options)


def test_runtime_defaults_to_one_active_batch(monkeypatch):
    monkeypatch.delenv("MAX_ACTIVE_BATCHES", raising=False)
    assert Settings.from_env().max_active_batches == 1
    monkeypatch.setenv("MAX_ACTIVE_BATCHES", "25")
    assert Settings.from_env().max_active_batches == 25


def test_secret_file_and_local_dev_only(monkeypatch, tmp_path):
    path = tmp_path / "key"
    path.write_text("a" * 32 + "\n")
    monkeypatch.setenv("INTERNAL_API_KEY_FILE", str(path))
    monkeypatch.setenv("PLATFORM_CALLBACK_ORIGIN", "http://127.0.0.1:8010")
    monkeypatch.setenv("ALLOW_LOCAL_CALLBACKS", "true")
    assert Settings.from_env().internal_api_key.get_secret_value() == "a" * 32
    monkeypatch.setenv("INTERNAL_API_KEY", "other")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_engine_imports_are_public_and_sqlite_only_in_control_plane():
    import prospector_service

    root = Path(prospector_service.__file__).parent
    for file in root.rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(("prospector_engine.engines", "prospector_cli"))
            if isinstance(node, ast.Import) and node.names[0].name == "sqlite3":
                assert file.name in {"metadata.py", "main.py", "coordinator.py"}


@pytest.mark.parametrize("value", ("", "true", "2"))
def test_protected_setting_must_be_explicit(monkeypatch, value):
    monkeypatch.setenv("PROSPECTOR_CHROMIUM_SANDBOX", value)
    with pytest.raises(ValidationError):
        Settings.from_env()
