import os
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, model_validator


class Settings(BaseModel):
    app_env: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    internal_api_key: SecretStr | None = None
    platform_callback_origin: str | None = None
    callback_api_key: SecretStr | None = None
    allow_local_callbacks: bool = False
    engine_browser: Literal["msedge", "chromium"] = "msedge"
    engine_headless: bool = False
    engine_worker_concurrency: int = Field(default=1, ge=1, le=1)
    queue_capacity: int = Field(default=16, ge=1, le=1000)
    max_registered_jobs: int = Field(default=100, ge=1, le=10000)
    max_request_bytes: int = Field(default=65536, ge=1024, le=1048576)
    max_result_bytes: int = Field(default=1048576, ge=1024, le=16777216)
    callback_timeout: float = Field(default=5, gt=0, le=60)
    callback_max_attempts: int = Field(default=3, ge=1, le=10)
    callback_backoff: float = Field(default=0.25, ge=0, le=10)
    shutdown_grace_seconds: float = Field(default=10, gt=0, le=300)

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.app_env == "production" and self.allow_local_callbacks:
            raise ValueError("local callbacks are unavailable in production")
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
                or origin != origin.strip()
                or "\\" in origin
                or "%" in origin
            ):
                raise ValueError("callback origin must be a configured HTTP(S) origin")
            if parsed.scheme != "https" and not (
                local and self.allow_local_callbacks and self.app_env != "production"
            ):
                raise ValueError("HTTP callbacks require explicit local development configuration")
            if local and not self.allow_local_callbacks:
                raise ValueError("local callbacks must be explicitly enabled")
            # Validate port now; never defer malformed port to a worker.
            parsed.port
        return self

    @property
    def credentials_configured(self) -> bool:
        return all(
            value and value.get_secret_value().strip()
            for value in (self.internal_api_key, self.callback_api_key)
        )

    @classmethod
    def from_env(cls) -> "Settings":
        values = {}
        for key in cls.model_fields:
            value = os.environ.get(key.upper())
            if value is not None:
                if key in {"internal_api_key", "callback_api_key", "platform_callback_origin"}:
                    value = value or None
                values[key] = value
        return cls(**values)
