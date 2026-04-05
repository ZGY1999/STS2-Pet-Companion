from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


DEFAULT_CONFIG_FILE_NAME = "sts2_pet.toml"


@dataclass(frozen=True, slots=True)
class OrchestratorConfig:
    game_base_url: str = "http://127.0.0.1:15526"
    pet_base_url: str = "http://127.0.0.1:15526"
    game_state_path: str = "/api/v1/singleplayer"
    game_action_path: str = "/api/v1/singleplayer"
    pet_status_path: str = "/api/v1/pet/status"
    pet_mode_path: str = "/api/v1/pet/mode"
    pet_message_path: str = "/api/v1/pet/message"
    timeout_seconds: float = 90.0
    poll_interval_seconds: float = 0.75
    debug_logging: bool = False
    provider_name: str = "deterministic"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    codex_cmd: str = "codex.cmd"
    codex_model: str | None = None
    claude_cmd: str = "claude"
    claude_model: str | None = None

    @classmethod
    def default_config_path(cls, cwd: str | os.PathLike[str] | None = None) -> Path:
        root = Path.cwd() if cwd is None else Path(cwd)
        return root / DEFAULT_CONFIG_FILE_NAME

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> "OrchestratorConfig":
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        if tomllib is None:
            raise RuntimeError("tomllib is not available in this Python runtime")

        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RuntimeError("Config file must parse to a TOML table")

        merged = {}
        merged.update(_normalize_mapping(raw))
        merged.update(_normalize_mapping(raw.get("orchestrator")))
        merged.update(_normalize_mapping(raw.get("provider")))
        return cls().with_overrides(merged)

    @classmethod
    def from_env(cls) -> "OrchestratorConfig":
        return cls().with_overrides(_env_overrides())

    @classmethod
    def from_sources(
        cls,
        *,
        config_file: str | os.PathLike[str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
    ) -> "OrchestratorConfig":
        config = cls()
        resolved_file = Path(config_file) if config_file else cls.default_config_path(cwd)
        if resolved_file.exists():
            config = cls.from_file(resolved_file)
        return config.with_overrides(_env_overrides())

    def with_overrides(self, overrides: Mapping[str, Any]) -> "OrchestratorConfig":
        normalized = {key: value for key, value in _normalize_mapping(overrides).items() if value is not None}
        return replace(self, **normalized) if normalized else self


def _normalize_mapping(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}

    result: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, Mapping):
            continue
        canonical = _canonical_key(str(key))
        if canonical is None:
            continue
        if canonical in {"timeout_seconds", "poll_interval_seconds"}:
            result[canonical] = _maybe_float(value)
        elif canonical == "debug_logging":
            result[canonical] = _maybe_bool(value)
        else:
            result[canonical] = value
    return result


def _canonical_key(key: str) -> str | None:
    normalized = key.strip().lower().replace("-", "_")
    aliases = {
        "provider": "provider_name",
        "provider_name": "provider_name",
        "api_key": "openai_api_key",
        "openai_api_key": "openai_api_key",
        "base_url": "openai_base_url",
        "openai_base_url": "openai_base_url",
        "model": "openai_model",
        "openai_model": "openai_model",
        "codex_cmd": "codex_cmd",
        "codex_model": "codex_model",
        "claude_cmd": "claude_cmd",
        "claude_model": "claude_model",
        "game_base_url": "game_base_url",
        "pet_base_url": "pet_base_url",
        "game_state_path": "game_state_path",
        "game_action_path": "game_action_path",
        "pet_status_path": "pet_status_path",
        "pet_mode_path": "pet_mode_path",
        "pet_message_path": "pet_message_path",
        "timeout_seconds": "timeout_seconds",
        "poll_interval_seconds": "poll_interval_seconds",
        "debug_logging": "debug_logging",
    }
    return aliases.get(normalized)


def _maybe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _maybe_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Cannot interpret boolean value from {value!r}")


def _env_overrides() -> dict[str, Any]:
    return {
        "game_base_url": os.getenv("STS2_PET_GAME_BASE_URL"),
        "pet_base_url": os.getenv("STS2_PET_PET_BASE_URL"),
        "game_state_path": os.getenv("STS2_PET_GAME_STATE_PATH"),
        "game_action_path": os.getenv("STS2_PET_GAME_ACTION_PATH"),
        "pet_status_path": os.getenv("STS2_PET_STATUS_PATH"),
        "pet_mode_path": os.getenv("STS2_PET_MODE_PATH"),
        "pet_message_path": os.getenv("STS2_PET_MESSAGE_PATH"),
        "timeout_seconds": _maybe_float(os.getenv("STS2_PET_TIMEOUT_SECONDS")),
        "poll_interval_seconds": _maybe_float(os.getenv("STS2_PET_POLL_INTERVAL_SECONDS")),
        "debug_logging": _maybe_bool(os.getenv("STS2_PET_DEBUG_LOGGING")),
        "provider_name": os.getenv("STS2_PET_PROVIDER"),
        "openai_api_key": os.getenv("STS2_PET_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"),
        "openai_base_url": os.getenv("STS2_PET_BASE_URL") or os.getenv("OPENAI_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL"),
        "openai_model": os.getenv("STS2_PET_MODEL") or os.getenv("OPENAI_MODEL") or os.getenv("ANTHROPIC_MODEL"),
        "codex_cmd": os.getenv("STS2_PET_CODEX_CMD"),
        "codex_model": os.getenv("STS2_PET_CODEX_MODEL"),
        "claude_cmd": os.getenv("STS2_PET_CLAUDE_CMD"),
        "claude_model": os.getenv("STS2_PET_CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL"),
    }
