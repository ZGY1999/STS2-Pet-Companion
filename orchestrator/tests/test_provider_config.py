from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sts2_pet.config import OrchestratorConfig
from sts2_pet.cli import build_parser
from sts2_pet.models import Snapshot
from sts2_pet.provider import (
    AnthropicCompatibleProvider,
    ClaudeCliProvider,
    CodexCliProvider,
    DeterministicProvider,
    OpenAICompatibleProvider,
    JsonPromptProvider,
    _build_user_prompt,
    create_default_provider,
)


def test_create_default_provider_uses_deterministic_by_default() -> None:
    provider = create_default_provider(OrchestratorConfig())

    assert isinstance(provider, DeterministicProvider)


def test_create_default_provider_builds_openai_compatible_provider() -> None:
    provider = create_default_provider(
        OrchestratorConfig(
            provider_name="openai_compatible",
            openai_api_key="test-key",
            openai_base_url="https://example.test/v1",
            openai_model="gpt-test",
        )
    )

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "https://example.test/v1"
    assert provider.model == "gpt-test"


def test_create_default_provider_builds_anthropic_compatible_provider() -> None:
    provider = create_default_provider(
        OrchestratorConfig(
            provider_name="anthropic_compatible",
            openai_api_key="test-key",
            openai_base_url="https://example.test/claude",
            openai_model="claude-sonnet-test",
        )
    )

    assert isinstance(provider, AnthropicCompatibleProvider)
    assert provider.base_url == "https://example.test/claude"
    assert provider.model == "claude-sonnet-test"


def test_create_default_provider_builds_codex_provider() -> None:
    provider = create_default_provider(
        OrchestratorConfig(
            provider_name="codex_cli",
            codex_cmd="codex.cmd",
            codex_model="gpt-5-codex",
            timeout_seconds=7.5,
        )
    )

    assert isinstance(provider, CodexCliProvider)
    assert provider.command == "codex.cmd"
    assert provider.model == "gpt-5-codex"
    assert provider.timeout_seconds == 7.5


def test_create_default_provider_builds_claude_cli_provider() -> None:
    provider = create_default_provider(
        OrchestratorConfig(
            provider_name="claude_cli",
            claude_cmd="claude",
            claude_model="claude-sonnet-4-6",
            timeout_seconds=11.0,
        )
    )

    assert isinstance(provider, ClaudeCliProvider)
    assert provider.command == "claude"
    assert provider.model == "claude-sonnet-4-6"
    assert provider.timeout_seconds == 11.0


def test_openai_provider_requires_gateway_configuration() -> None:
    try:
        create_default_provider(OrchestratorConfig(provider_name="gateway"))
    except RuntimeError as error:
        assert "API_KEY" in str(error)
    else:
        raise AssertionError("Expected missing gateway configuration to raise")


def test_config_can_load_from_toml_file() -> None:
    sandbox_dir = Path(__file__).resolve().parent / f".config-test-{uuid4().hex}"
    sandbox_dir.mkdir()
    try:
        config_path = sandbox_dir / "sts2_pet.toml"
        config_path.write_text(
            """
provider_name = "openai_compatible"
poll_interval_seconds = 1.25
debug_logging = true

[provider]
api_key = "file-key"
base_url = "https://gateway.example/v1"
model = "gpt-test"
""".strip(),
            encoding="utf-8",
        )

        config = OrchestratorConfig.from_sources(config_file=config_path)

        assert config.provider_name == "openai_compatible"
        assert config.poll_interval_seconds == 1.25
        assert config.debug_logging is True
        assert config.openai_api_key == "file-key"
        assert config.openai_base_url == "https://gateway.example/v1"
        assert config.openai_model == "gpt-test"
    finally:
        config_path.unlink(missing_ok=True)
        sandbox_dir.rmdir()


def test_cli_defaults_can_come_from_config_file() -> None:
    config = OrchestratorConfig(
        provider_name="codex_cli",
        codex_cmd="custom-codex.cmd",
        codex_model="gpt-5-codex",
        poll_interval_seconds=2.5,
    )

    parser = build_parser(config)
    args = parser.parse_args([])

    assert args.provider == "codex_cli"
    assert args.codex_cmd == "custom-codex.cmd"
    assert args.codex_model == "gpt-5-codex"
    assert args.poll_interval_seconds == 2.5


def test_cli_accepts_debug_logging_flag() -> None:
    parser = build_parser(OrchestratorConfig())

    args = parser.parse_args(["--debug-logging"])

    assert args.debug_logging is True


def test_cli_accepts_anthropic_provider_choice() -> None:
    parser = build_parser(OrchestratorConfig())

    args = parser.parse_args(["--provider", "anthropic_compatible"])

    assert args.provider == "anthropic_compatible"


def test_cli_accepts_claude_cli_provider_choice() -> None:
    parser = build_parser(OrchestratorConfig())

    args = parser.parse_args(
        ["--provider", "claude_cli", "--claude-cmd", "claude", "--claude-model", "claude-sonnet-4-6"]
    )

    assert args.provider == "claude_cli"
    assert args.claude_cmd == "claude"
    assert args.claude_model == "claude-sonnet-4-6"


def test_example_config_file_is_valid_toml() -> None:
    example_path = Path(__file__).resolve().parents[1] / "sts2_pet.toml.example"

    config = OrchestratorConfig.from_file(example_path)

    assert config.provider_name == "deterministic"
    assert config.poll_interval_seconds == 0.75
    assert config.timeout_seconds == 90


def test_build_user_prompt_compacts_large_combat_state() -> None:
    snapshot = Snapshot(
        state_type="monster",
        raw_state={
            "state_type": "monster",
            "battle": {
                "round": 3,
                "turn": "player",
            },
            "player": {
                "hp": 42,
                "max_hp": 70,
                "energy": 2,
                "max_energy": 3,
                "draw_pile_count": 14,
                "discard_pile_count": 22,
                "exhaust_pile_count": 1,
                "hand": [
                    {"index": 0, "name": "Strike", "cost": "1", "description": "Deal 6 damage."},
                    {"index": 1, "name": "Defend", "cost": "1", "description": "Gain 5 block."},
                ],
                "draw_pile": [{"name": f"Draw {index}"} for index in range(20)],
                "discard_pile": [{"name": f"Discard {index}"} for index in range(20)],
                "relics": [{"name": f"Relic {index}", "description": "Text"} for index in range(8)],
            },
            "battle_log": [f"log-{index}" for index in range(30)],
        },
    )

    prompt = _build_user_prompt(snapshot, "auto")

    assert '"state_type":"monster"' in prompt
    assert '"discard_pile_count":22' in prompt
    assert '"hand"' in prompt
    assert '"discard_pile": [' not in prompt
    assert '"battle_log"' not in prompt


def test_build_user_prompt_trims_low_value_combat_fields_but_keeps_tactical_data() -> None:
    snapshot = Snapshot(
        state_type="monster",
        raw_state={
            "state_type": "monster",
            "battle": {
                "round": 3,
                "turn": "player",
                "is_play_phase": True,
                "enemies": [
                    {
                        "entity_id": "JAW_WORM_0",
                        "combat_id": 7,
                        "name": "Jaw Worm",
                        "hp": 40,
                        "max_hp": 40,
                        "block": 0,
                        "status": [],
                        "intents": [
                            {
                                "type": "Attack",
                                "label": "11",
                                "title": "Chomp",
                                "description": "Deal 11 damage.",
                            }
                        ],
                    }
                ],
            },
            "player": {
                "hp": 55,
                "max_hp": 70,
                "block": 0,
                "energy": 3,
                "max_energy": 3,
                "hand": [
                    {
                        "index": 0,
                        "id": "STRIKE_SILENT",
                        "name": "Strike",
                        "cost": "1",
                        "star_cost": None,
                        "description": "Deal 6 damage.",
                        "target_type": "AnyEnemy",
                        "can_play": True,
                        "unplayable_reason": None,
                        "is_upgraded": False,
                        "keywords": [
                            {"name": "Damage", "description": "Repeated explanation."}
                        ],
                    }
                ],
                "relics": [
                    {
                        "id": "RING_OF_THE_SNAKE",
                        "name": "Ring of the Snake",
                        "description": "At the start of each combat, draw 2 additional cards.",
                        "counter": None,
                        "keywords": [
                            {"name": "Draw", "description": "Repeated explanation."}
                        ],
                    }
                ],
                "draw_pile_count": 8,
                "discard_pile_count": 2,
                "exhaust_pile_count": 0,
            },
        },
    )

    prompt = _build_user_prompt(snapshot, "auto")

    assert '"entity_id":"JAW_WORM_0"' in prompt
    assert '"energy":3' in prompt
    assert '"description":"Deal 6 damage."' in prompt
    assert '"keywords"' not in prompt
    assert '"id":"STRIKE_SILENT"' not in prompt
    assert '"counter":null' not in prompt
    assert '"star_cost":null' not in prompt
    assert '"unplayable_reason":null' not in prompt


def test_build_user_prompt_lists_allowed_actions_for_rewards_state() -> None:
    snapshot = Snapshot(
        state_type="rewards",
        raw_state={
            "state_type": "rewards",
            "rewards": {
                "items": [
                    {"index": 0, "kind": "card_reward"},
                    {"index": 1, "kind": "gold"},
                ]
            },
        },
    )

    prompt = _build_user_prompt(snapshot, "auto")

    assert "Allowed actions for this state" in prompt
    assert "claim_reward" in prompt
    assert "proceed" in prompt
    assert "select_reward" not in prompt


def test_build_user_prompt_includes_parameter_hints_for_map_state() -> None:
    snapshot = Snapshot(
        state_type="map",
        raw_state={
            "state_type": "map",
            "next_options": [
                {"index": 0, "type": "monster"},
            ],
        },
    )

    prompt = _build_user_prompt(snapshot, "auto")

    assert "choose_map_node" in prompt
    assert '"index"' in prompt
    assert "node_index" in prompt


def test_build_user_prompt_warns_that_event_state_must_not_use_proceed() -> None:
    snapshot = Snapshot(
        state_type="event",
        raw_state={
            "state_type": "event",
            "event": {
                "in_dialogue": False,
                "options": [{"index": 0, "title": "Proceed"}],
            },
        },
    )

    prompt = _build_user_prompt(snapshot, "auto")

    assert "Never use proceed on event screens" in prompt
    assert "choose_event_option" in prompt


def test_json_prompt_provider_normalizes_original_mcp_tool_names_and_params() -> None:
    class StaticJsonProvider(JsonPromptProvider):
        def _complete_json(self, *, system_prompt: str, user_prompt: str):
            return {
                "action": "map_choose_node",
                "params": {"node_index": 0},
                "narration_title": "选路",
                "narration_lines": ["选最稳的路线。"],
            }

    provider = StaticJsonProvider()

    plan = provider.plan(
        Snapshot(
            state_type="map",
            raw_state={"state_type": "map"},
        )
    )

    assert plan is not None
    assert plan.action == "choose_map_node"
    assert dict(plan.params) == {"index": 0}


def test_json_prompt_provider_normalizes_low_risk_aliases_and_wrapped_actions() -> None:
    class StaticJsonProvider(JsonPromptProvider):
        def _complete_json(self, *, system_prompt: str, user_prompt: str):
            return {
                "action": '"select_reward"',
                "params": {"reward_index": 1},
                "narration_title": "领奖励",
                "narration_lines": ["先拿最有价值的奖励。"],
            }

    provider = StaticJsonProvider()

    plan = provider.plan(
        Snapshot(
            state_type="rewards",
            raw_state={"state_type": "rewards"},
        )
    )

    assert plan is not None
    assert plan.action == "claim_reward"
    assert dict(plan.params) == {"index": 1}


def test_deterministic_provider_uses_advance_dialogue_for_event_dialogue() -> None:
    provider = DeterministicProvider()

    plan = provider.plan(
        Snapshot(
            state_type="event",
            raw_state={
                "state_type": "event",
                "event": {
                    "in_dialogue": True,
                    "options": [],
                },
            },
        )
    )

    assert plan is not None
    assert plan.action == "advance_dialogue"


def test_deterministic_provider_uses_only_event_option_when_unambiguous() -> None:
    provider = DeterministicProvider()

    plan = provider.plan(
        Snapshot(
            state_type="event",
            raw_state={
                "state_type": "event",
                "event": {
                    "in_dialogue": False,
                    "options": [
                        {"index": 3, "title": "Proceed", "disabled": False},
                    ],
                },
            },
        )
    )

    assert plan is not None
    assert plan.action == "choose_event_option"
    assert dict(plan.params) == {"index": 3}


def test_codex_provider_uses_utf8_stdin(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 4321
        returncode = 0

        def communicate(self, input: str, timeout: float) -> tuple[str, str]:
            captured["input"] = input
            captured["timeout"] = timeout
            return ("", "")

        def poll(self) -> int:
            return self.returncode

        def kill(self) -> None:
            pass

    def fake_popen(command: list[str], **kwargs):
        captured["command"] = command
        captured["encoding"] = kwargs["encoding"]
        output_index = command.index("--output-last-message") + 1
        Path(command[output_index]).write_text('{"action":"end_turn"}', encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr("sts2_pet.provider.subprocess.Popen", fake_popen)

    provider = CodexCliProvider(command="codex.cmd", timeout_seconds=7.5, model="gpt-5-codex")
    result = provider.plan(Snapshot(state_type="monster", raw_state={"state_type": "monster"}))

    assert captured["encoding"] == "utf-8"
    assert captured["timeout"] == 7.5
    assert result.action == "end_turn"


def test_claude_cli_provider_uses_print_json_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 9876
        returncode = 0

        def communicate(self, input: str | None = None, timeout: float | None = None) -> tuple[str, str]:
            captured["input"] = input
            captured["timeout"] = timeout
            return ('{"action":"end_turn","params":{}}', "")

        def poll(self) -> int:
            return self.returncode

        def kill(self) -> None:
            pass

    def fake_popen(command: list[str], **kwargs):
        captured["command"] = command
        captured["encoding"] = kwargs["encoding"]
        return FakeProcess()

    monkeypatch.setattr("sts2_pet.provider.subprocess.Popen", fake_popen)

    provider = ClaudeCliProvider(command="claude", timeout_seconds=9.0, model="claude-sonnet-4-6")
    result = provider.plan(Snapshot(state_type="monster", raw_state={"state_type": "monster"}))

    assert captured["encoding"] == "utf-8"
    assert captured["timeout"] == 9.0
    assert isinstance(captured["input"], str)
    assert "Return only valid JSON." in captured["input"]
    assert "Allowed actions for this state: play_card, use_potion, end_turn." in captured["input"]
    assert 'Game state JSON:\n{"state_type":"monster"}' in captured["input"]
    assert captured["command"] == [
        "cmd",
        "/c",
        "claude",
        "-p",
        "--output-format",
        "json",
        "--input-format",
        "text",
        "--permission-mode",
        "bypassPermissions",
        "--tools",
        "",
        "--model",
        "claude-sonnet-4-6",
    ]
    assert result.action == "end_turn"


def test_anthropic_provider_uses_messages_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"content":[{"type":"text","text":"{\\"action\\":\\"end_turn\\",\\"params\\":{}}"}]}'

    def fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("sts2_pet.provider.urlopen", fake_urlopen)

    provider = AnthropicCompatibleProvider(
        api_key="anthropic-key",
        base_url="https://example.test/claude",
        model="claude-sonnet-test",
        timeout_seconds=12.5,
    )

    result = provider.plan(Snapshot(state_type="monster", raw_state={"state_type": "monster"}))

    assert captured["url"] == "https://example.test/claude/v1/messages"
    headers = {str(k).lower(): str(v) for k, v in dict(captured["headers"]).items()}
    assert headers["x-api-key"] == "anthropic-key"
    assert headers["authorization"] == "Bearer anthropic-key"
    assert headers["anthropic-version"] == "2023-06-01"
    assert captured["timeout"] == 12.5
    assert '"system"' in str(captured["body"])
    assert result.action == "end_turn"


def test_anthropic_provider_preserves_custom_base_url_endpoint(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"content":[{"type":"text","text":"{\\"action\\":\\"end_turn\\",\\"params\\":{}}"}]}'

    def fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr("sts2_pet.provider.urlopen", fake_urlopen)

    provider = AnthropicCompatibleProvider(
        api_key="anthropic-key",
        base_url="https://code.newcli.com/claude/super",
        model="claude-sonnet-test",
        timeout_seconds=12.5,
    )

    result = provider.plan(Snapshot(state_type="monster", raw_state={"state_type": "monster"}))

    assert captured["url"] == "https://code.newcli.com/claude/super"
    assert result.action == "end_turn"
