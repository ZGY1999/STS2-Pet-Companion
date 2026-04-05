from __future__ import annotations

import argparse
import sys
import time
from typing import Sequence

from .config import OrchestratorConfig
from .models import Mode
from .runner import create_runner


def build_parser(base_config: OrchestratorConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="STS2 pet orchestrator")
    parser.add_argument("--config-file", default=None)
    parser.add_argument("--game-base-url", default=base_config.game_base_url)
    parser.add_argument("--pet-base-url", default=base_config.pet_base_url)
    parser.add_argument("--game-state-path", default=base_config.game_state_path)
    parser.add_argument("--game-action-path", default=base_config.game_action_path)
    parser.add_argument("--pet-status-path", default=base_config.pet_status_path)
    parser.add_argument("--pet-mode-path", default=base_config.pet_mode_path)
    parser.add_argument("--pet-message-path", default=base_config.pet_message_path)
    parser.add_argument("--timeout-seconds", type=float, default=base_config.timeout_seconds)
    parser.add_argument("--poll-interval-seconds", type=float, default=base_config.poll_interval_seconds)
    parser.add_argument(
        "--debug-logging",
        action=argparse.BooleanOptionalAction,
        default=base_config.debug_logging,
        help="Emit verbose orchestrator logs to stdout/stderr.",
    )
    parser.add_argument(
        "--provider",
        choices=["deterministic", "openai_compatible", "gateway", "anthropic_compatible", "codex_cli", "claude_cli"],
        default=base_config.provider_name,
    )
    parser.add_argument("--api-key", default=base_config.openai_api_key)
    parser.add_argument("--base-url", default=base_config.openai_base_url)
    parser.add_argument("--model", default=base_config.openai_model)
    parser.add_argument("--codex-cmd", default=base_config.codex_cmd)
    parser.add_argument("--codex-model", default=base_config.codex_model)
    parser.add_argument("--claude-cmd", default=base_config.claude_cmd)
    parser.add_argument("--claude-model", default=base_config.claude_model)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single tick and exit instead of staying attached to the pet bridge.",
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in Mode],
        help="Set the initial bridge mode before the loop starts.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--config-file", default=None)
    bootstrap_args, _ = bootstrap.parse_known_args(argv)
    base_config = OrchestratorConfig.from_sources(config_file=bootstrap_args.config_file)
    args = build_parser(base_config).parse_args(argv)
    config = OrchestratorConfig(
        game_base_url=args.game_base_url,
        pet_base_url=args.pet_base_url,
        game_state_path=args.game_state_path,
        game_action_path=args.game_action_path,
        pet_status_path=args.pet_status_path,
        pet_mode_path=args.pet_mode_path,
        pet_message_path=args.pet_message_path,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        debug_logging=args.debug_logging,
        provider_name=args.provider,
        openai_api_key=args.api_key,
        openai_base_url=args.base_url,
        openai_model=args.model,
        codex_cmd=args.codex_cmd,
        codex_model=args.codex_model,
        claude_cmd=args.claude_cmd,
        claude_model=args.claude_model,
    )
    runner = create_runner(config)
    mode_override = Mode(args.mode) if args.mode is not None else None

    if args.once:
        runner.run_once(mode_override=mode_override)
        return 0

    if mode_override is not None:
        runner.run_once(mode_override=mode_override)

    try:
        while True:
            runner.run_once()
            time.sleep(max(config.poll_interval_seconds, 0.1))
    except KeyboardInterrupt:
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
