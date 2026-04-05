from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping

from .config import OrchestratorConfig
from .game_client import GameClient
from .models import Mode, Snapshot
from .pet_client import PetClient, PetMessage
from .policy import should_generate_advice
from .provider import ActionPlan, DeterministicProvider, Provider, create_default_provider

COMBAT_STATES = {"monster", "elite", "boss"}
PASSIVE_STATES = {"menu", "overlay", "unknown"}
LEGAL_ACTIONS_BY_STATE: dict[str, set[str]] = {
    "monster": {"play_card", "use_potion", "end_turn"},
    "elite": {"play_card", "use_potion", "end_turn"},
    "boss": {"play_card", "use_potion", "end_turn"},
    "hand_select": {"combat_select_card", "combat_confirm_selection", "use_potion"},
    "rewards": {"claim_reward", "proceed", "use_potion"},
    "card_reward": {"select_card_reward", "skip_card_reward", "use_potion"},
    "map": {"choose_map_node", "use_potion"},
    "event": {"choose_event_option", "advance_dialogue", "use_potion"},
    "rest_site": {"choose_rest_option", "proceed", "use_potion"},
    "shop": {"shop_purchase", "proceed", "use_potion"},
    "treasure": {"claim_treasure_relic", "proceed", "use_potion"},
    "card_select": {"select_card", "confirm_selection", "cancel_selection", "use_potion"},
    "bundle_select": {"select_bundle", "confirm_bundle_selection", "cancel_bundle_selection"},
    "relic_select": {"select_relic", "skip_relic_selection", "use_potion"},
    "crystal_sphere": {"crystal_sphere_set_tool", "crystal_sphere_click_cell", "crystal_sphere_proceed"},
}


@dataclass(frozen=True, slots=True)
class RunResult:
    mode: Mode
    acted: bool
    stopped_for_mode_change: bool = False
    reason: str = ""


class Runner:
    def __init__(
        self,
        config: OrchestratorConfig,
        *,
        game_client: GameClient | None = None,
        pet_client: PetClient | None = None,
        provider: Provider | None = None,
    ) -> None:
        self._config = config
        self._game_client = game_client or GameClient(
            config.game_base_url,
            config.game_state_path,
            config.game_action_path,
            timeout_seconds=config.timeout_seconds,
        )
        self._pet_client = pet_client or PetClient(
            config.pet_base_url,
            config.pet_status_path,
            config.pet_mode_path,
            config.pet_message_path,
            timeout_seconds=config.timeout_seconds,
        )
        self._provider = provider or create_default_provider(config)
        self._fallback_provider = DeterministicProvider()
        self._last_mode: Mode | None = None
        self._last_advise_state_key: str | None = None
        self._last_nonadvise_state_key: str | None = None
        self._last_auto_plan_state_key: str | None = None
        self._last_auto_plan: ActionPlan | None = None
        self._last_auto_action_key: str | None = None
        self._last_error_key: str | None = None
        self._inferred_card_select_by_raw_state_key: dict[str, tuple[int, ...]] = {}

    def run_once(self, mode_override: Mode | None = None) -> RunResult:
        mode = self._resolve_mode(mode_override)
        self._reset_caches_for_mode(mode)
        if mode is Mode.PAUSE:
            return RunResult(mode=mode, acted=False, reason="paused")

        state_read_started = time.perf_counter()
        raw_state = self._game_client.get_state()
        self._debug_elapsed("state_read", state_read_started)
        raw_state_key = self._state_key(raw_state)
        state = self._apply_inferred_transient_state(raw_state, raw_state_key)
        state_key = self._state_key(state)
        snapshot = self._snapshot_from_game_state(state)
        self._debug("tick", mode=mode.value, state_type=snapshot.state_type)

        if snapshot.state_type != "card_select":
            self._inferred_card_select_by_raw_state_key.clear()

        if mode is Mode.ADVISE:
            return self._run_advise_mode(mode, snapshot, state_key)

        if mode is Mode.AUTO:
            return self._run_auto_mode(mode, snapshot, state_key, raw_state_key, mode_override)

        return RunResult(mode=mode, acted=False, reason="unsupported_mode")

    def _run_advise_mode(self, mode: Mode, snapshot: Snapshot, state_key: str) -> RunResult:
        if self._last_advise_state_key == state_key:
            return RunResult(mode=mode, acted=False, reason="awaiting_state_change")

        if not should_generate_advice(mode, snapshot):
            if self._last_nonadvise_state_key != state_key:
                self._pet_client.set_message(PetMessage(mode=mode, state="idle", title="", lines=()))
                self._last_nonadvise_state_key = state_key
                return RunResult(mode=mode, acted=True, reason="advice_cleared")
            return RunResult(mode=mode, acted=False, reason="advice_not_needed")

        self._last_nonadvise_state_key = None
        had_previous_advice = self._last_advise_state_key is not None
        if not had_previous_advice:
            self._pet_client.set_message(
                PetMessage(
                    mode=mode,
                    state="thinking",
                    title="正在分析",
                    lines=("我先看一下这一手和当前局面。",),
                )
            )

        provider_started = time.perf_counter()
        try:
            advice = self._require_provider().advise(snapshot)
        except Exception as error:
            self._debug_elapsed("provider_advise", provider_started, state_type=snapshot.state_type, outcome="error")
            if had_previous_advice:
                self._debug("advise_refresh_failed", error=str(error))
                return RunResult(mode=mode, acted=False, reason="advice_refresh_failed")
            return self._handle_provider_error(mode, state_key, error)
        self._debug_elapsed("provider_advise", provider_started, state_type=snapshot.state_type, outcome="ok")

        if self._mode_from_status() is not mode:
            return RunResult(
                mode=mode,
                acted=False,
                stopped_for_mode_change=True,
                reason="mode_changed_after_provider",
            )

        if advice is None:
            if had_previous_advice:
                return RunResult(mode=mode, acted=False, reason="advice_refresh_failed")
            self._pet_client.set_message(PetMessage(mode=mode, state="idle", title="", lines=()))
            self._last_advise_state_key = state_key
            return RunResult(mode=mode, acted=True, reason="advice_cleared")

        self._pet_client.set_message(
            PetMessage(
                mode=mode,
                state="talking",
                title=advice.title,
                lines=advice.lines,
            )
        )
        self._last_advise_state_key = state_key
        return RunResult(mode=mode, acted=True, reason="advice_sent")

    def _run_auto_mode(
        self,
        mode: Mode,
        snapshot: Snapshot,
        state_key: str,
        raw_state_key: str,
        mode_override: Mode | None,
    ) -> RunResult:
        try:
            plan = self._plan_for_auto_mode(snapshot, state_key)
        except Exception as error:
            return self._handle_provider_error(mode, state_key, error)

        if plan is None:
            return RunResult(mode=mode, acted=False, reason="no_action")

        if mode_override is None and self._mode_from_status() is not Mode.AUTO:
            return RunResult(
                mode=mode,
                acted=False,
                stopped_for_mode_change=True,
                reason="mode_changed_before_action",
            )

        action_key = self._action_key(state_key, plan)
        if self._last_auto_action_key == action_key:
            return RunResult(mode=mode, acted=False, reason="awaiting_state_change")

        self._pet_client.set_message(
            PetMessage(
                mode=mode,
                state="auto_running",
                title=plan.narration_title,
                lines=plan.narration_lines,
            )
        )
        self._debug("auto_plan", state_type=snapshot.state_type, action=plan.action, params=dict(plan.params))

        if mode_override is None:
            current_mode = self._mode_from_status()
            if current_mode is not Mode.AUTO:
                self._pet_client.set_message(
                    PetMessage(
                        mode=current_mode,
                        state=self._visual_state_for_mode(current_mode),
                        title="",
                        lines=(),
                    )
                )
                return RunResult(
                    mode=mode,
                    acted=False,
                    stopped_for_mode_change=True,
                    reason="mode_changed_before_action",
                )

        action_started = time.perf_counter()
        try:
            result = self._game_client.post_action(plan.action, **dict(plan.params))
        except Exception as error:
            self._invalidate_auto_plan_cache(state_key)
            self._debug_elapsed(
                "action_post",
                action_started,
                action=plan.action,
                state_type=snapshot.state_type,
                outcome="error",
            )
            if self._should_ignore_stale_action_error(raw_state_key):
                return RunResult(mode=mode, acted=False, reason="stale_action_ignored")
            return self._handle_provider_error(mode, state_key, error)
        self._debug_elapsed(
            "action_post",
            action_started,
            action=plan.action,
            state_type=snapshot.state_type,
            outcome="ok",
        )

        self._remember_successful_transient_action(snapshot, raw_state_key, plan)
        self._debug("auto_action_ok", action=plan.action, params=dict(plan.params), result=dict(result))
        self._last_auto_action_key = action_key
        return RunResult(mode=mode, acted=True, reason="action_executed")

    def _plan_for_auto_mode(self, snapshot: Snapshot, state_key: str) -> ActionPlan | None:
        if self._last_auto_plan_state_key == state_key and self._last_auto_plan is not None:
            self._debug("provider_plan_cache_hit", state_type=snapshot.state_type)
            return self._last_auto_plan

        if snapshot.state_type in PASSIVE_STATES:
            return None
        if snapshot.state_type in COMBAT_STATES:
            if not self._is_player_action_phase(snapshot):
                return None
            plan = self._plan_for_combat(snapshot)
        else:
            plan = self._plan_for_noncombat(snapshot)

        self._last_auto_plan_state_key = state_key
        self._last_auto_plan = plan
        return plan

    def _plan_for_combat(self, snapshot: Snapshot) -> ActionPlan:
        provider_started = time.perf_counter()
        try:
            plan = self._require_provider().plan(snapshot)
        except Exception as error:
            self._debug_elapsed("provider_plan", provider_started, state_type=snapshot.state_type, outcome="error")
            raise RuntimeError(
                f"Failed to plan action for state '{snapshot.state_type}': {error}"
            ) from error
        self._debug_elapsed("provider_plan", provider_started, state_type=snapshot.state_type, outcome="ok")

        if plan is None:
            raise RuntimeError(f"No automatic action available for state '{snapshot.state_type}'.")

        plan = self._normalize_plan_for_snapshot(snapshot, plan)
        illegal_reason = self._illegal_action_reason(snapshot, plan)
        if illegal_reason is not None:
            raise RuntimeError(illegal_reason)
        return plan

    def _plan_for_noncombat(self, snapshot: Snapshot) -> ActionPlan:
        provider_started = time.perf_counter()
        try:
            plan = self._require_provider().plan(snapshot)
        except Exception as error:
            self._debug_elapsed("provider_plan", provider_started, state_type=snapshot.state_type, outcome="error")
            raise RuntimeError(
                f"Failed to plan action for state '{snapshot.state_type}': {error}"
            ) from error
        self._debug_elapsed("provider_plan", provider_started, state_type=snapshot.state_type, outcome="ok")

        if plan is None:
            raise RuntimeError(f"No automatic action available for state '{snapshot.state_type}'.")

        plan = self._normalize_plan_for_snapshot(snapshot, plan)
        illegal_reason = self._illegal_action_reason(snapshot, plan)
        if illegal_reason is not None:
            raise RuntimeError(illegal_reason)
        return plan

    def _illegal_action_reason(self, snapshot: Snapshot, plan: ActionPlan) -> str | None:
        allowed_actions = LEGAL_ACTIONS_BY_STATE.get(snapshot.state_type)
        if not allowed_actions:
            return f"No automatic action mapping exists for state '{snapshot.state_type}'."
        if plan.action in allowed_actions:
            return None
        allowed = ", ".join(sorted(allowed_actions))
        return (
            f"Action '{plan.action}' is not valid for state '{snapshot.state_type}'. "
            f"Allowed actions: {allowed}."
        )

    def _normalize_plan_for_snapshot(self, snapshot: Snapshot, plan: ActionPlan) -> ActionPlan:
        if snapshot.state_type != "event" or plan.action != "proceed":
            return plan

        raw_state = snapshot.raw_state if isinstance(snapshot.raw_state, Mapping) else {}
        event_state = raw_state.get("event") if isinstance(raw_state.get("event"), Mapping) else raw_state
        if not isinstance(event_state, Mapping):
            return plan

        if bool(event_state.get("in_dialogue")):
            return ActionPlan(
                action="advance_dialogue",
                params={},
                narration_title=plan.narration_title,
                narration_lines=plan.narration_lines,
            )

        options = event_state.get("options")
        if not isinstance(options, list):
            return plan

        unlocked = [
            option for option in options
            if isinstance(option, Mapping)
            and option.get("index") is not None
            and option.get("disabled") is not True
        ]
        if len(unlocked) != 1:
            return plan

        return ActionPlan(
            action="choose_event_option",
            params={"index": unlocked[0]["index"]},
            narration_title=plan.narration_title,
            narration_lines=plan.narration_lines,
        )

    def _is_player_action_phase(self, snapshot: Snapshot) -> bool:
        raw_state = snapshot.raw_state if isinstance(snapshot.raw_state, Mapping) else {}
        battle = raw_state.get("battle")
        if not isinstance(battle, Mapping):
            return True

        is_play_phase = battle.get("is_play_phase")
        if isinstance(is_play_phase, bool) and not is_play_phase:
            return False

        turn = battle.get("turn")
        if turn is None:
            return True
        return str(turn).strip().lower() == "player"

    def _resolve_mode(self, mode_override: Mode | None) -> Mode:
        if mode_override is not None:
            self._pet_client.set_mode(mode_override)
            return mode_override
        return self._mode_from_status()

    def _mode_from_status(self) -> Mode:
        status = self._pet_client.get_status()
        raw_mode = status.get("mode", status.get("state", Mode.PAUSE.value))
        try:
            return Mode(str(raw_mode))
        except ValueError:
            return Mode.PAUSE

    def _reset_caches_for_mode(self, mode: Mode) -> None:
        if self._last_mode is mode:
            return

        self._last_mode = mode
        self._last_advise_state_key = None
        self._last_nonadvise_state_key = None
        self._last_auto_plan_state_key = None
        self._last_auto_plan = None
        self._last_auto_action_key = None
        self._last_error_key = None

    def _invalidate_auto_plan_cache(self, state_key: str | None = None) -> None:
        if state_key is None or self._last_auto_plan_state_key == state_key:
            self._last_auto_plan_state_key = None
            self._last_auto_plan = None

    def _snapshot_from_game_state(self, state: Mapping[str, object]) -> Snapshot:
        return Snapshot(
            state_type=str(state.get("state_type", "unknown")),
            raw_state=state,
        )

    def _apply_inferred_transient_state(
        self,
        raw_state: Mapping[str, object],
        raw_state_key: str,
    ) -> Mapping[str, object]:
        if str(raw_state.get("state_type", "unknown")) != "card_select":
            return raw_state

        inferred = self._inferred_card_select_by_raw_state_key.get(raw_state_key)
        if not inferred:
            return raw_state

        state = json.loads(json.dumps(raw_state, ensure_ascii=False))
        card_select = state.get("card_select")
        if not isinstance(card_select, dict):
            return raw_state

        cards = card_select.get("cards")
        if isinstance(cards, list):
            selected_cards: list[dict[str, object]] = []
            for card in cards:
                if not isinstance(card, dict):
                    continue
                index = card.get("index")
                is_selected = isinstance(index, int) and index in inferred
                if is_selected:
                    card["is_selected"] = True
                    selected_cards.append({
                        "index": index,
                        "name": card.get("name"),
                    })
                elif "is_selected" not in card:
                    card["is_selected"] = False

            card_select["selected_cards"] = selected_cards
            card_select["selected_count"] = len(selected_cards)

            required = self._required_card_select_count(card_select)
            if required is not None and len(selected_cards) >= required:
                card_select["can_confirm"] = bool(card_select.get("can_confirm")) or True

        return state

    def _remember_successful_transient_action(
        self,
        snapshot: Snapshot,
        raw_state_key: str,
        plan: ActionPlan,
    ) -> None:
        if snapshot.state_type != "card_select" or plan.action != "select_card":
            return

        index = plan.params.get("index")
        if not isinstance(index, int):
            return

        existing = self._inferred_card_select_by_raw_state_key.get(raw_state_key, ())
        if index in existing:
            return

        self._inferred_card_select_by_raw_state_key[raw_state_key] = (*existing, index)
        self._last_auto_plan_state_key = None
        self._last_auto_plan = None
        self._last_auto_action_key = None

    def _should_ignore_stale_action_error(self, raw_state_key: str) -> bool:
        try:
            latest_state = self._game_client.get_state()
        except Exception:
            return False

        latest_raw_state_key = self._state_key(latest_state)
        if latest_raw_state_key == raw_state_key:
            return False

        self._invalidate_auto_plan_cache()
        self._last_auto_action_key = None
        self._last_error_key = None
        self._inferred_card_select_by_raw_state_key.clear()
        self._debug("stale_action_ignored")
        return True

    @staticmethod
    def _required_card_select_count(card_select: Mapping[str, object]) -> int | None:
        prompt = card_select.get("prompt")
        if not isinstance(prompt, str):
            return None

        match = re.search(r"(\d+)", prompt)
        if match is None:
            return None

        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _state_key(self, state: Mapping[str, object]) -> str:
        return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _action_key(self, state_key: str, plan: ActionPlan) -> str:
        payload = {
            "state_key": state_key,
            "action": plan.action,
            "params": dict(plan.params),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _visual_state_for_mode(self, mode: Mode) -> str:
        return "paused" if mode is Mode.PAUSE else "idle"

    def _require_provider(self) -> Provider:
        if self._provider is None:
            raise RuntimeError("A provider is required for advise and auto modes.")
        return self._provider

    def _handle_provider_error(self, mode: Mode, state_key: str, error: Exception) -> RunResult:
        summary = self._summarize_error(error)
        error_key = f"{mode.value}:{state_key}:{summary}"
        if self._last_error_key != error_key:
            self._pet_client.set_message(
                PetMessage(
                    mode=mode,
                    state="error",
                    title="AI 出错了",
                    lines=(summary,),
                )
            )
            self._last_error_key = error_key
        self._debug("provider_error", mode=mode.value, error=summary)
        return RunResult(mode=mode, acted=False, reason="provider_error")

    @staticmethod
    def _summarize_error(error: Exception) -> str:
        message = str(error).strip()
        if not message:
            return "AI 调用失败，但没有返回错误信息。"

        first_line = message.splitlines()[0].strip()
        lowered = message.lower()
        if "timed out" in lowered or "timeout" in lowered:
            return "AI 响应超时，请稍后重试。"
        if "not supported" in lowered:
            return "当前配置的模型不支持本地 Codex。"
        if "invalid refresh token" in lowered:
            return "本地 Codex 登录已过期，需要重新登录。"
        if "command line is too long" in lowered or "输入行太长" in message:
            return "发给 Codex 的状态太长了，请缩小上下文后重试。"
        if len(first_line) > 160:
            return first_line[:157] + "..."
        return first_line

    def _debug(self, event: str, **fields: Any) -> None:
        if not self._config.debug_logging:
            return
        payload = {"event": event, **fields}
        print(f"[sts2_pet] {json.dumps(payload, ensure_ascii=False, sort_keys=True)}", flush=True)

    def _debug_elapsed(self, event: str, started_at: float, **fields: Any) -> None:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
        self._debug(event, elapsed_ms=elapsed_ms, **fields)


def create_runner(config: OrchestratorConfig) -> Runner:
    return Runner(config, provider=create_default_provider(config))
