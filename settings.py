"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_ops_directory() -> Path:
    return Path.home() / ".copilot-ops"


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


@dataclass(frozen=True)
class AppSettings:
    """Runtime configuration with conservative local-development defaults."""

    host: str = "127.0.0.1"
    port: int = 8000
    model: str = "auto"
    request_timeout_seconds: float = 60.0
    max_message_length: int = 10_000
    audit_logging: bool = True
    log_directory: Path = field(
        default_factory=lambda: _default_ops_directory() / "logs"
    )
    copilot_base_directory: Path = field(
        default_factory=lambda: _default_ops_directory() / "copilot"
    )
    cors_origins: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> AppSettings:
        """Build settings from ``COPILOT_OPS_*`` environment variables."""

        origins = tuple(
            origin.strip()
            for origin in os.getenv("COPILOT_OPS_CORS_ORIGINS", "").split(",")
            if origin.strip()
        )
        settings = cls(
            host=os.getenv("COPILOT_OPS_HOST", "127.0.0.1"),
            port=int(os.getenv("COPILOT_OPS_PORT", "8000")),
            model=os.getenv("COPILOT_OPS_MODEL", "auto"),
            request_timeout_seconds=float(
                os.getenv("COPILOT_OPS_REQUEST_TIMEOUT_SECONDS", "60")
            ),
            max_message_length=int(
                os.getenv("COPILOT_OPS_MAX_MESSAGE_LENGTH", "10000")
            ),
            audit_logging=_read_bool("COPILOT_OPS_AUDIT_LOGGING", True),
            log_directory=Path(
                os.getenv(
                    "COPILOT_OPS_LOG_DIRECTORY",
                    str(_default_ops_directory() / "logs"),
                )
            ).expanduser(),
            copilot_base_directory=Path(
                os.getenv(
                    "COPILOT_OPS_COPILOT_DIRECTORY",
                    str(_default_ops_directory() / "copilot"),
                )
            ).expanduser(),
            cors_origins=origins,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not 1 <= self.port <= 65_535:
            raise ValueError("COPILOT_OPS_PORT must be between 1 and 65535")
        if self.request_timeout_seconds <= 0:
            raise ValueError("COPILOT_OPS_REQUEST_TIMEOUT_SECONDS must be positive")
        if self.max_message_length <= 0:
            raise ValueError("COPILOT_OPS_MAX_MESSAGE_LENGTH must be positive")
