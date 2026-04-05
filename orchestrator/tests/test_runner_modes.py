from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sts2_pet.config import OrchestratorConfig
from sts2_pet.models import Mode, Snapshot
from sts2_pet.provider import ActionPlan, AdviceBubble, Provider
from sts2_pet.runner import Runner


class FakeGameClient:
    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        self.read_calls = 0
        self.actions: list[tuple[str, dict[str, object]]] = []

    def get_state(self) -> dict[str, object]:
        self.read_calls += 1
        if self.snapshot.raw_state is not None:
            return dict(self.snapshot.raw_state)
        return {"state_type": self.snapshot.state_type}

    def post_action(self, action: str, **params: object) -> dict[str, object]:
        self.actions.append((action, dict(params)))
        return {"status": "ok"}


class SequencedGameClient:
    def __init__(self, states: list[dict[str, object]]) -> None:
        self.states = list(states)
        self.read_calls = 0
        self.actions: list[tuple[str, dict[str, object]]] = []

    def get_state(self) -> dict[str, object]:
        self.read_calls += 1
        if len(self.states) > 1:
            return self.states.pop(0)
        return self.states[0]

    def post_action(self, action: str, **params: object) -> dict[str, object]:
        self.actions.append((action, dict(params)))
        return {"status": "ok"}


class ErroringGameClient(FakeGameClient):
    def __init__(self, snapshot: Snapshot, *, error_message: str) -> None:
        super().__init__(snapshot)
        self.error_message = error_message

    def post_action(self, action: str, **params: object) -> dict[str, object]:
        self.actions.append((action, dict(params)))
        raise RuntimeError(self.error_message)


class FakePetClient:
    def __init__(self, modes: list[Mode]) -> None:
        self.statuses = [{"mode": mode.value} for mode in modes]
        self.read_calls = 0
        self.messages: list[object] = []
        self.mode_sets: list[Mode | str] = []

    def get_status(self) -> dict[str, object]:
        self.read_calls += 1
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]

    def set_mode(self, mode: Mode | str) -> dict[str, object]:
        self.mode_sets.append(mode)
        return {"status": "ok"}

    def set_message(self, message: object) -> dict[str, object]:
        self.messages.append(message)
        return {"status": "ok"}


class FakeProvider(Provider):
    def __init__(self, advice: AdviceBubble | None = None, plan: ActionPlan | None = None) -> None:
        self.advice_value = advice
        self.plan_value = plan
        self.advice_calls = 0
        self.plan_calls = 0

    def advise(self, snapshot: Snapshot) -> AdviceBubble | None:
        self.advice_calls += 1
        return self.advice_value

    def plan(self, snapshot: Snapshot) -> ActionPlan | None:
        self.plan_calls += 1
        return self.plan_value


class RaisingProvider(Provider):
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.advice_calls = 0
        self.plan_calls = 0

    def advise(self, snapshot: Snapshot) -> AdviceBubble | None:
        self.advice_calls += 1
        raise self.error

    def plan(self, snapshot: Snapshot) -> ActionPlan | None:
        self.plan_calls += 1
        raise self.error


def test_pause_mode_skips_clients_and_provider() -> None:
    runner = Runner(
        OrchestratorConfig(),
        game_client=FakeGameClient(Snapshot(state_type="monster")),
        pet_client=FakePetClient([Mode.PAUSE]),
        provider=FakeProvider(),
    )

    result = runner.run_once()

    assert result.mode is Mode.PAUSE
    assert result.acted is False
    assert result.reason == "paused"


def test_advise_mode_pushes_full_bubble_for_supported_state() -> None:
    game_client = FakeGameClient(Snapshot(state_type="card_reward"))
    pet_client = FakePetClient([Mode.ADVISE])
    provider = FakeProvider(advice=AdviceBubble(title="Take the card", lines=("Pick a strong upgrade target.",)))

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.ADVISE
    assert result.acted is True
    assert result.reason == "advice_sent"
    assert game_client.read_calls == 1
    assert provider.advice_calls == 1
    assert len(pet_client.messages) == 2
    assert pet_client.messages[0].state == "thinking"
    assert pet_client.messages[1].state == "talking"


def test_advise_mode_waits_for_state_change_before_repeating() -> None:
    game_client = FakeGameClient(Snapshot(state_type="card_reward"))
    pet_client = FakePetClient([Mode.ADVISE, Mode.ADVISE])
    provider = FakeProvider(advice=AdviceBubble(title="Take the card", lines=("Pick a strong upgrade target.",)))

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    first = runner.run_once()
    second = runner.run_once()

    assert first.reason == "advice_sent"
    assert second.mode is Mode.ADVISE
    assert second.acted is False
    assert second.reason == "awaiting_state_change"
    assert provider.advice_calls == 1
    assert len(pet_client.messages) == 2


def test_advise_mode_keeps_existing_advice_when_refresh_times_out() -> None:
    game_client = SequencedGameClient([
        {"state_type": "monster", "battle": {"round": 1}},
        {"state_type": "monster", "battle": {"round": 2}},
    ])
    pet_client = FakePetClient([Mode.ADVISE, Mode.ADVISE])

    class FlakyProvider(Provider):
        def __init__(self) -> None:
            self.calls = 0

        def advise(self, snapshot: Snapshot) -> AdviceBubble | None:
            self.calls += 1
            if self.calls == 1:
                return AdviceBubble(title="Attack first", lines=("Focus the weakest target.",))
            raise RuntimeError("Gateway timed out after 20.0s")

        def plan(self, snapshot: Snapshot) -> ActionPlan | None:
            raise AssertionError("plan should not be called in advise mode")

    provider = FlakyProvider()
    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    first = runner.run_once()
    second = runner.run_once()

    assert first.reason == "advice_sent"
    assert second.mode is Mode.ADVISE
    assert second.acted is False
    assert second.reason == "advice_refresh_failed"
    assert len(pet_client.messages) == 2
    assert pet_client.messages[1].title == "Attack first"


def test_advise_mode_keeps_previous_advice_visible_while_refreshing() -> None:
    game_client = SequencedGameClient([
        {"state_type": "monster", "battle": {"round": 1}},
        {"state_type": "monster", "battle": {"round": 2}},
    ])
    pet_client = FakePetClient([Mode.ADVISE, Mode.ADVISE])
    provider = FakeProvider(
        advice=AdviceBubble(title="Attack first", lines=("Focus the weakest target.",))
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    first = runner.run_once()
    second = runner.run_once()

    assert first.reason == "advice_sent"
    assert second.reason == "advice_sent"
    assert provider.advice_calls == 2
    assert len(pet_client.messages) == 3
    assert pet_client.messages[0].state == "thinking"
    assert pet_client.messages[1].state == "talking"
    assert pet_client.messages[2].state == "talking"


def test_auto_mode_reports_provider_failure_outside_combat_without_switching_modes() -> None:
    game_client = FakeGameClient(Snapshot(state_type="map"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = RaisingProvider(RuntimeError("Gateway timed out after 20.0s"))

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is False
    assert result.reason == "provider_error"
    assert provider.plan_calls == 1
    assert pet_client.mode_sets == []
    assert game_client.actions == []
    assert len(pet_client.messages) == 1
    assert pet_client.messages[0].state == "error"


def test_auto_mode_reports_provider_failure_in_combat_without_acting() -> None:
    game_client = FakeGameClient(Snapshot(state_type="monster"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = RaisingProvider(RuntimeError("Gateway timed out after 20.0s"))

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is False
    assert result.reason == "provider_error"
    assert provider.plan_calls == 1
    assert pet_client.mode_sets == []
    assert game_client.actions == []
    assert len(pet_client.messages) == 1
    assert pet_client.messages[0].state == "error"


def test_auto_mode_rejects_illegal_action_for_current_state() -> None:
    game_client = FakeGameClient(Snapshot(state_type="event"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = FakeProvider(
        plan=ActionPlan(
            action="proceed",
            narration_title="Try to continue",
            narration_lines=("This should not be legal on an event screen.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is False
    assert result.reason == "provider_error"
    assert pet_client.mode_sets == []
    assert game_client.actions == []
    assert len(pet_client.messages) == 1
    assert pet_client.messages[0].state == "error"
    assert "event" in pet_client.messages[0].lines[0]
    assert "proceed" in pet_client.messages[0].lines[0]


def test_auto_mode_normalizes_event_proceed_to_advance_dialogue() -> None:
    game_client = FakeGameClient(
        Snapshot(
            state_type="event",
            raw_state={
                "state_type": "event",
                "event": {
                    "in_dialogue": True,
                    "body": "Ancient dialogue",
                    "options": [],
                },
            },
        )
    )
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = FakeProvider(
        plan=ActionPlan(
            action="proceed",
            narration_title="Continue",
            narration_lines=("Advance the dialogue.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is True
    assert result.reason == "action_executed"
    assert game_client.actions == [("advance_dialogue", {})]


def test_auto_mode_normalizes_event_proceed_to_only_unlocked_option() -> None:
    game_client = FakeGameClient(
        Snapshot(
            state_type="event",
            raw_state={
                "state_type": "event",
                "event": {
                    "in_dialogue": False,
                    "options": [
                        {"index": 2, "title": "Proceed", "disabled": False},
                    ],
                },
            },
        )
    )
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = FakeProvider(
        plan=ActionPlan(
            action="proceed",
            narration_title="Continue",
            narration_lines=("Take the only option.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is True
    assert result.reason == "action_executed"
    assert game_client.actions == [("choose_event_option", {"index": 2})]


def test_auto_mode_ignores_transient_overlay_state_without_error() -> None:
    game_client = FakeGameClient(Snapshot(state_type="overlay"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = FakeProvider()

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is False
    assert result.reason == "no_action"
    assert provider.plan_calls == 0
    assert game_client.actions == []
    assert pet_client.messages == []


def test_auto_mode_does_not_act_during_enemy_turn() -> None:
    game_client = FakeGameClient(
        Snapshot(
            state_type="monster",
            raw_state={
                "state_type": "monster",
                "battle": {
                    "turn": "enemy",
                    "is_play_phase": False,
                },
            },
        )
    )
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = FakeProvider(
        plan=ActionPlan(
            action="end_turn",
            narration_title="Skip",
            narration_lines=("Should not happen during enemy turn.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is False
    assert result.reason == "no_action"
    assert provider.plan_calls == 0
    assert game_client.actions == []
    assert pet_client.messages == []


def test_auto_mode_surfaces_game_action_failure_without_switching_modes() -> None:
    game_client = ErroringGameClient(
        Snapshot(state_type="event"),
        error_message="Action 'choose_event_option' failed for state 'event': option index 0 is locked",
    )
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = FakeProvider(
        plan=ActionPlan(
            action="choose_event_option",
            params={"index": 0},
            narration_title="Pick the option",
            narration_lines=("Trying the first event option.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is False
    assert result.reason == "provider_error"
    assert pet_client.mode_sets == []
    assert game_client.actions == [("choose_event_option", {"index": 0})]
    assert len(pet_client.messages) == 2
    assert pet_client.messages[1].state == "error"
    assert "choose_event_option" in pet_client.messages[1].lines[0]
    assert "option index 0 is locked" in pet_client.messages[1].lines[0]


def test_timeout_summary_does_not_claim_fallback_advice() -> None:
    summary = Runner._summarize_error(RuntimeError("Gateway timed out after 20.0s"))

    assert summary == "AI 响应超时，请稍后重试。"


def test_advise_mode_clears_bubble_when_state_no_longer_needs_advice() -> None:
    game_client = FakeGameClient(Snapshot(state_type="overlay"))
    pet_client = FakePetClient([Mode.ADVISE])
    provider = FakeProvider(advice=AdviceBubble(title="Unused", lines=("Should not happen.",)))

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.ADVISE
    assert result.acted is True
    assert result.reason == "advice_cleared"
    assert provider.advice_calls == 0
    assert len(pet_client.messages) == 1
    assert pet_client.messages[0].state == "idle"
    assert pet_client.messages[0].title == ""
    assert pet_client.messages[0].lines == ()


def test_auto_mode_pushes_narration_and_executes_one_action() -> None:
    game_client = FakeGameClient(Snapshot(state_type="monster"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = FakeProvider(
        plan=ActionPlan(
            action="end_turn",
            params={"target": "front"},
            narration_title="End the turn",
            narration_lines=("No safe attack is available.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is True
    assert result.reason == "action_executed"
    assert game_client.actions == [("end_turn", {"target": "front"})]
    assert len(pet_client.messages) == 1
    assert provider.plan_calls == 1


def test_auto_mode_waits_for_state_change_before_repeating_action() -> None:
    game_client = FakeGameClient(Snapshot(state_type="monster"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO, Mode.AUTO, Mode.AUTO])
    provider = FakeProvider(
        plan=ActionPlan(
            action="end_turn",
            narration_title="End the turn",
            narration_lines=("No safe attack is available.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    first = runner.run_once()
    second = runner.run_once()

    assert first.reason == "action_executed"
    assert second.mode is Mode.AUTO
    assert second.acted is False
    assert second.reason == "awaiting_state_change"
    assert provider.plan_calls == 1
    assert game_client.actions == [("end_turn", {})]
    assert len(pet_client.messages) == 1


def test_auto_mode_stops_before_action_if_mode_changes() -> None:
    game_client = FakeGameClient(Snapshot(state_type="monster"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO, Mode.PAUSE])
    provider = FakeProvider(
        plan=ActionPlan(
            action="end_turn",
            narration_title="Thinking",
            narration_lines=("Waiting on the current mode.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is False
    assert result.stopped_for_mode_change is True
    assert result.reason == "mode_changed_before_action"
    assert len(pet_client.messages) == 2
    assert pet_client.messages[0].state == "auto_running"
    assert pet_client.messages[1].mode is Mode.PAUSE
    assert pet_client.messages[1].state == "paused"
    assert pet_client.messages[1].title == ""
    assert pet_client.messages[1].lines == ()
    assert game_client.actions == []


def test_advise_mode_uses_default_provider_when_omitted() -> None:
    game_client = FakeGameClient(Snapshot(state_type="card_reward"))
    pet_client = FakePetClient([Mode.ADVISE])

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
    )

    result = runner.run_once()

    assert result.mode is Mode.ADVISE
    assert result.acted is True
    assert result.reason == "advice_sent"
    assert len(pet_client.messages) == 2
    assert pet_client.messages[0].state == "thinking"
    assert pet_client.messages[1].state == "talking"


def test_auto_mode_uses_default_provider_when_omitted() -> None:
    game_client = FakeGameClient(Snapshot(state_type="monster"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
    )

    result = runner.run_once()

    assert result.mode is Mode.AUTO
    assert result.acted is True
    assert result.reason == "action_executed"
    assert game_client.actions == [("end_turn", {})]
    assert len(pet_client.messages) == 1


def test_mode_override_syncs_through_set_mode_before_acting() -> None:
    game_client = FakeGameClient(Snapshot(state_type="monster"))
    pet_client = FakePetClient([Mode.PAUSE])

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
    )

    result = runner.run_once(mode_override=Mode.AUTO)

    assert result.mode is Mode.AUTO
    assert result.acted is True
    assert pet_client.mode_sets == [Mode.AUTO]
    assert game_client.actions == [("end_turn", {})]


def test_invalid_status_mode_falls_back_to_pause() -> None:
    game_client = FakeGameClient(Snapshot(state_type="monster"))
    pet_client = FakePetClient([Mode.PAUSE])
    pet_client.statuses = [{"mode": "not-a-real-mode"}]
    provider = FakeProvider(
        advice=AdviceBubble(title="Unused", lines=("Should not happen.",)),
        plan=ActionPlan(action="end_turn"),
    )

    runner = Runner(
        OrchestratorConfig(),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    assert result.mode is Mode.PAUSE
    assert result.acted is False
    assert result.reason == "paused"
    assert game_client.read_calls == 0
    assert game_client.actions == []
    assert provider.advice_calls == 0
    assert provider.plan_calls == 0


def test_auto_mode_emits_timing_logs_when_debug_enabled(capsys) -> None:
    game_client = FakeGameClient(Snapshot(state_type="monster"))
    pet_client = FakePetClient([Mode.AUTO, Mode.AUTO])
    provider = FakeProvider(
        plan=ActionPlan(
            action="end_turn",
            narration_title="End the turn",
            narration_lines=("No safe attack is available.",),
        )
    )

    runner = Runner(
        OrchestratorConfig(debug_logging=True),
        game_client=game_client,
        pet_client=pet_client,
        provider=provider,
    )

    result = runner.run_once()

    captured = capsys.readouterr()
    assert result.reason == "action_executed"
    assert '"event": "state_read"' in captured.out
    assert '"event": "provider_plan"' in captured.out
    assert '"event": "action_post"' in captured.out
    assert '"elapsed_ms"' in captured.out
