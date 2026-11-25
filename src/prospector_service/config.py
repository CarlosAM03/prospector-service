import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, model_validator


class Settings(BaseModel):
    app_env: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    solution_id: str = "prospector-solution"
    assertion_issuer: str = "platform"
    assertion_audience: str = "prospector-service/v1"
    internal_api_key: SecretStr | None = None
    assertion_key: SecretStr | None = None
    metadata_key: SecretStr | None = None
    callback_api_key: SecretStr | None = None
    platform_callback_origin: str | None = None
    platform_callback_ca_file: Path | None = None
    allow_local_callbacks: bool = False
    metadata_path: Path = Path("data/prospector.sqlite3")
    engine_browser: Literal["msedge", "chromium"] = "chromium"
    engine_headless: bool = True
    worker_temp_dir: Path = Path("/dev/shm")
    max_request_bytes: int = Field(default=65536, ge=1024, le=65536)
    max_snapshot_bytes: int = Field(default=1048576, ge=1024, le=4194304)
    snapshot_budget_bytes: int = Field(default=134217728, ge=1024, le=1073741824)
    max_snapshots: int = Field(default=2048, ge=1, le=10000)
    ipc_max_bytes: int = Field(default=8388608, ge=65536, le=33554432)
    export_concurrency: int = Field(default=4, ge=1, le=25)
    max_export_bytes: int = Field(default=4194304, ge=1024, le=33554432)
    max_pending_callback_jobs: int = Field(default=1024, ge=125, le=10000)
    callback_timeout: float = Field(default=3, gt=0, le=30)
    callback_max_attempts: int = Field(default=3, ge=1, le=5)
    callback_backoff: float = Field(default=0.25, ge=0, le=5)

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.app_env == "production" and self.allow_local_callbacks:
            raise ValueError("local callbacks are unavailable in production")
        keys = [
            key.get_secret_value()
            for key in (
                self.internal_api_key,
                self.assertion_key,
                self.metadata_key,
                self.callback_api_key,
            )
            if key is not None
        ]
        if any(len(key.encode()) < 32 or key != key.strip() for key in keys):
            raise ValueError("each configured key must contain at least 32 bytes")
        if len(keys) != len(set(keys)):
            raise ValueError("credentials must be distinct")
        if self.platform_callback_origin:
            origin = self.platform_callback_origin
            if any(ord(char) <= 32 or ord(char) == 127 for char in origin):
                raise ValueError("callback origin contains invalid characters")
            parsed = urlsplit(origin)
            local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            if (
                parsed.scheme not in {"https", "http"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or "\\" in origin
                or "%" in origin
            ):
                raise ValueError("invalid callback origin")
            if local and not self.allow_local_callbacks:
                raise ValueError("local callbacks must be explicitly enabled")
            if parsed.scheme != "https" and not (local and self.allow_local_callbacks):
                raise ValueError("HTTPS is required for remote callbacks")
            parsed.port
        return self

    @property
    def credentials_configured(self) -> bool:
        return all(
            (
                self.internal_api_key,
                self.assertion_key,
                self.metadata_key,
                self.callback_api_key,
                self.platform_callback_origin,
            )
        )

    @classmethod
    def from_env(cls) -> "Settings":
        values = {}
        for field in cls.model_fields:
            value = os.environ.get(field.upper())
            key_file = os.environ.get(f"{field.upper()}_FILE") if field.endswith("_key") else None
            if key_file and value:
                raise ValueError("configure one credential source")
            if key_file:
                value = Path(key_file).read_text(encoding="utf-8").rstrip("\r\n")
            if value:
                values[field] = value
        return cls(**values)
