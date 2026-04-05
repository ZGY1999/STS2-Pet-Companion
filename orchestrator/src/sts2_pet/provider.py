from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import OrchestratorConfig
from .models import Snapshot
from .policy import ADVICE_STATES

ALLOWED_ACTIONS_BY_STATE: dict[str, tuple[str, ...]] = {
    "monster": ("play_card", "use_potion", "end_turn"),
    "elite": ("play_card", "use_potion", "end_turn"),
    "boss": ("play_card", "use_potion", "end_turn"),
    "hand_select": ("combat_select_card", "combat_confirm_selection", "use_potion"),
    "rewards": ("claim_reward", "proceed", "use_potion"),
    "card_reward": ("select_card_reward", "skip_card_reward", "use_potion"),
    "map": ("choose_map_node", "use_potion"),
    "event": ("choose_event_option", "advance_dialogue", "use_potion"),
    "rest_site": ("choose_rest_option", "proceed", "use_potion"),
    "shop": ("shop_purchase", "proceed", "use_potion"),
    "treasure": ("claim_treasure_relic", "proceed", "use_potion"),
    "card_select": ("select_card", "confirm_selection", "cancel_selection", "use_potion"),
    "bundle_select": ("select_bundle", "confirm_bundle_selection", "cancel_bundle_selection"),
    "relic_select": ("select_relic", "skip_relic_selection", "use_potion"),
    "crystal_sphere": ("crystal_sphere_set_tool", "crystal_sphere_click_cell", "crystal_sphere_proceed"),
}

ACTION_PARAMETER_HINTS: dict[str, tuple[str, ...]] = {
    "play_card": (
        'Use params {"card_index": <hand index>} for non-targeted cards.',
        'If the card needs a target, add {"target": "<entity_id>"}.',
    ),
    "use_potion": (
        'Use params {"slot": <potion slot index>}.',
        'If the potion needs a target, add {"target": "<entity_id>"}.',
    ),
    "claim_reward": ('Use params {"index": <reward index>}.',),
    "select_card_reward": ('Use params {"card_index": <reward card index>}.',),
    "choose_map_node": (
        'Use params {"index": <next_options index>}.',
        'The original MCP alias was map_choose_node(node_index=...).',
    ),
    "choose_event_option": ('Use params {"index": <event option index>}.',),
    "choose_rest_option": ('Use params {"index": <rest option index>}.',),
    "shop_purchase": ('Use params {"index": <shop item index>}.',),
    "select_card": ('Use params {"index": <card index>}.',),
    "select_bundle": ('Use params {"index": <bundle index>}.',),
    "select_relic": ('Use params {"index": <relic index>}.',),
    "claim_treasure_relic": ('Use params {"index": <relic index>}.',),
    "combat_select_card": ('Use params {"card_index": <hand index>}.',),
    "crystal_sphere_set_tool": ('Use params {"tool": "big" | "small"}.',),
    "crystal_sphere_click_cell": ('Use params {"x": <cell x>, "y": <cell y>}.',),
}

ACTION_ALIASES: dict[str, str] = {
    "combat_play_card": "play_card",
    "combat_end_turn": "end_turn",
    "map_choose_node": "choose_map_node",
    "event_choose_option": "choose_event_option",
    "event_advance_dialogue": "advance_dialogue",
    "rest_choose_option": "choose_rest_option",
    "shop_purchase_item": "shop_purchase",
    "proceed_to_map": "proceed",
    "rewards_claim": "claim_reward",
    "select_reward": "claim_reward",
    "rewards_pick_card": "select_card_reward",
    "pick_card_reward": "select_card_reward",
    "rewards_skip_card": "skip_card_reward",
    "deck_select_card": "select_card",
    "deck_confirm_selection": "confirm_selection",
    "deck_cancel_selection": "cancel_selection",
    "bundle_confirm_selection": "confirm_bundle_selection",
    "bundle_cancel_selection": "cancel_bundle_selection",
    "relic_skip": "skip_relic_selection",
    "treasure_claim_relic": "claim_treasure_relic",
}

PARAM_ALIASES_BY_ACTION: dict[str, dict[str, str]] = {
    "choose_map_node": {"node_index": "index"},
    "choose_event_option": {"option_index": "index"},
    "choose_rest_option": {"option_index": "index"},
    "shop_purchase": {"item_index": "index"},
    "claim_reward": {"reward_index": "index"},
    "select_card": {"card_index": "index"},
    "select_bundle": {"bundle_index": "index"},
    "select_relic": {"relic_index": "index"},
    "claim_treasure_relic": {"relic_index": "index"},
}

@dataclass(frozen=True, slots=True)
class AdviceBubble:
    title: str
    lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionPlan:
    action: str
    params: Mapping[str, object] = field(default_factory=dict)
    narration_title: str = ""
    narration_lines: tuple[str, ...] = ()


class Provider(Protocol):
    def advise(self, snapshot: Snapshot) -> AdviceBubble | None: ...

    def plan(self, snapshot: Snapshot) -> ActionPlan | None: ...


@dataclass(frozen=True, slots=True)
class DeterministicProvider:
    """Minimal fallback provider for local smoke runs without an external model."""

    def advise(self, snapshot: Snapshot) -> AdviceBubble | None:
        if snapshot.state_type not in ADVICE_STATES:
            return None
        title = f"{snapshot.state_type} 建议"
        return AdviceBubble(
            title=title,
            lines=("优先选择当前页面里最稳、最省资源的原生选项。",)
        )

    def plan(self, snapshot: Snapshot) -> ActionPlan | None:
        if snapshot.state_type in {"monster", "elite", "boss"}:
            return ActionPlan(
                action="end_turn",
                narration_title="自动模式",
                narration_lines=("当前没有更稳的固定动作，先结束回合。",)
            )
        if snapshot.state_type == "event":
            event_state = snapshot.raw_state.get("event") if isinstance(snapshot.raw_state, Mapping) else None
            if not isinstance(event_state, Mapping):
                event_state = snapshot.raw_state if isinstance(snapshot.raw_state, Mapping) else {}

            if bool(event_state.get("in_dialogue")):
                return ActionPlan(
                    action="advance_dialogue",
                    narration_title="自动模式",
                    narration_lines=("先继续当前对话。",),
                )

            options = event_state.get("options")
            if isinstance(options, list):
                unlocked = [
                    option for option in options
                    if isinstance(option, Mapping)
                    and option.get("index") is not None
                    and option.get("disabled") is not True
                ]
                if len(unlocked) == 1:
                    return ActionPlan(
                        action="choose_event_option",
                        params={"index": unlocked[0]["index"]},
                        narration_title="自动模式",
                        narration_lines=("先选择唯一可用的事件选项。",),
                    )
            return None
        if snapshot.state_type == "card_reward":
            return ActionPlan(
                action="select_card_reward",
                params={"card_index": 0},
                narration_title="自动模式",
                narration_lines=("先按固定策略拿第一张牌。",)
            )
        if snapshot.state_type in ADVICE_STATES:
            return ActionPlan(
                action="proceed",
                narration_title="自动模式",
                narration_lines=("先继续当前页面。",)
            )
        return None


class JsonPromptProvider:
    def advise(self, snapshot: Snapshot) -> AdviceBubble | None:
        if snapshot.state_type not in ADVICE_STATES:
            return None

        payload = self._complete_json(
            system_prompt=ADVISE_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(snapshot, "advise"),
        )
        lines = _normalize_lines(payload.get("lines"))
        return AdviceBubble(
            title=str(payload.get("title", "寤鸿")).strip() or "寤鸿",
            lines=lines or ("优先选择当前页面里最稳、收益最高的选项。",)
        )

    def plan(self, snapshot: Snapshot) -> ActionPlan | None:
        payload = self._complete_json(
            system_prompt=AUTO_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(snapshot, "auto"),
        )
        action = _normalize_action_name(payload.get("action"))
        if not action:
            return None

        params = payload.get("params")
        if isinstance(params, dict):
            params = _normalize_action_params(action, params)
        return ActionPlan(
            action=action,
            params=params if isinstance(params, dict) else {},
            narration_title=str(payload.get("narration_title", "鑷姩妯″紡")).strip() or "鑷姩妯″紡",
            narration_lines=_normalize_lines(payload.get("narration_lines")) or ("执行下一步可行动作。",)
        )

    def _complete_json(self, *, system_prompt: str, user_prompt: str) -> Mapping[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider(JsonPromptProvider):
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float

    def _complete_json(self, *, system_prompt: str, user_prompt: str) -> Mapping[str, Any]:
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        request_payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI-compatible provider error HTTP {error.code}: {body}") from error

        payload = json.loads(raw)
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            raise RuntimeError("OpenAI-compatible provider returned no choices")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        return _parse_json_output(content)


@dataclass(frozen=True, slots=True)
class AnthropicCompatibleProvider(JsonPromptProvider):
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float

    def _complete_json(self, *, system_prompt: str, user_prompt: str) -> Mapping[str, Any]:
        endpoint = _anthropic_messages_endpoint(self.base_url)
        request_payload = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        }
        body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic-compatible provider error HTTP {error.code}: {body}") from error

        payload = json.loads(raw)
        content = payload.get("content", "")
        return _parse_json_output(content)


@dataclass(frozen=True, slots=True)
class CodexCliProvider(JsonPromptProvider):
    command: str
    timeout_seconds: float
    model: str | None = None

    def _complete_json(self, *, system_prompt: str, user_prompt: str) -> Mapping[str, Any]:
        working_root = Path.home()
        prompt = f"{system_prompt}\n\n{user_prompt}"

        with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False, encoding="utf-8") as handle:
            output_file = Path(handle.name)

        try:
            command = [
                *shlex.split(self.command, posix=False),
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--color",
                "never",
                "--output-last-message",
                str(output_file),
                "-C",
                str(working_root),
                "-",
            ]
            if self.model:
                command[1:1] = ["--model", self.model]

            process = subprocess.Popen(
                command,
                cwd=working_root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            try:
                stdout, stderr = process.communicate(prompt, timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired as error:
                _kill_process_tree(process)
                raise RuntimeError(
                    f"Codex provider timed out after {self.timeout_seconds:.1f}s"
                ) from error

            if process.returncode != 0:
                stderr = (stderr or "").strip()
                raise RuntimeError(
                    f"Codex provider failed with exit code {process.returncode}: {stderr}"
                )

            content = output_file.read_text(encoding="utf-8").strip()
            return _parse_json_output(content)
        finally:
            output_file.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class ClaudeCliProvider(JsonPromptProvider):
    command: str
    timeout_seconds: float
    model: str | None = None

    def _complete_json(self, *, system_prompt: str, user_prompt: str) -> Mapping[str, Any]:
        working_root = Path.home()
        prompt = f"{system_prompt}\n\n{user_prompt}"

        command = [
            "cmd",
            "/c",
            *shlex.split(self.command, posix=False),
            "-p",
            "--output-format",
            "json",
            "--input-format",
            "text",
            "--permission-mode",
            "bypassPermissions",
            "--tools",
            "",
        ]
        if self.model:
            command.extend(["--model", self.model])

        process = subprocess.Popen(
            command,
            cwd=working_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        try:
            stdout, stderr = process.communicate(prompt, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as error:
            _kill_process_tree(process)
            raise RuntimeError(
                f"Claude provider timed out after {self.timeout_seconds:.1f}s"
            ) from error

        if process.returncode != 0:
            stderr = (stderr or "").strip()
            raise RuntimeError(
                f"Claude provider failed with exit code {process.returncode}: {stderr}"
            )

        return _parse_claude_cli_output(stdout)


def create_default_provider(config: OrchestratorConfig) -> Provider:
    provider_name = (config.provider_name or "deterministic").strip().lower()
    if provider_name == "deterministic":
        return DeterministicProvider()

    if provider_name in {"openai", "openai_compatible", "gateway"}:
        if not config.openai_api_key:
            raise RuntimeError("STS2 pet provider requires STS2_PET_API_KEY or OPENAI_API_KEY")
        if not config.openai_base_url:
            raise RuntimeError("STS2 pet provider requires STS2_PET_BASE_URL or OPENAI_BASE_URL")
        if not config.openai_model:
            raise RuntimeError("STS2 pet provider requires STS2_PET_MODEL or OPENAI_MODEL")
        return OpenAICompatibleProvider(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.openai_model,
            timeout_seconds=config.timeout_seconds,
        )

    if provider_name == "anthropic_compatible":
        if not config.openai_api_key:
            raise RuntimeError(
                "STS2 pet provider requires STS2_PET_API_KEY, ANTHROPIC_AUTH_TOKEN, or OPENAI_API_KEY"
            )
        if not config.openai_base_url:
            raise RuntimeError(
                "STS2 pet provider requires STS2_PET_BASE_URL, ANTHROPIC_BASE_URL, or OPENAI_BASE_URL"
            )
        if not config.openai_model:
            raise RuntimeError("STS2 pet provider requires STS2_PET_MODEL, ANTHROPIC_MODEL, or OPENAI_MODEL")
        return AnthropicCompatibleProvider(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.openai_model,
            timeout_seconds=config.timeout_seconds,
        )

    if provider_name in {"codex", "codex_cli"}:
        return CodexCliProvider(
            command=config.codex_cmd,
            model=config.codex_model,
            timeout_seconds=max(config.timeout_seconds, 1.0),
        )

    if provider_name in {"claude", "claude_cli"}:
        return ClaudeCliProvider(
            command=config.claude_cmd,
            model=config.claude_model,
            timeout_seconds=max(config.timeout_seconds, 1.0),
        )

    raise RuntimeError(f"Unknown STS2 pet provider '{config.provider_name}'")


def _build_user_prompt(snapshot: Snapshot, mode: str) -> str:
    state_payload = _compact_state_payload(snapshot)
    state_json = json.dumps(state_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if mode == "advise":
        return (
            "You are the STS2 pet companion. Read the game state JSON and return only one JSON object "
            'with keys "title" and "lines". Keep lines short, concrete, and immediately actionable.\n\n'
            f"Game state JSON:\n{state_json}"
        )

    allowed_actions = ALLOWED_ACTIONS_BY_STATE.get(snapshot.state_type)
    allowed_actions_text = (
        f"\nAllowed actions for this state: {', '.join(allowed_actions)}.\n"
        if allowed_actions
        else ""
    )
    parameter_hints_text = _build_parameter_hints_text(allowed_actions)
    state_specific_constraints = _build_state_specific_constraints(snapshot)
    return (
        "You are the STS2 auto-play companion. Read the game state JSON and return only one JSON object "
        'with keys "action", "params", "narration_title", and "narration_lines". '
        "Choose exactly one next legal action for the current screen."
        f"{allowed_actions_text}{parameter_hints_text}{state_specific_constraints}\n"
        f"Game state JSON:\n{state_json}"
    )


def _compact_state_payload(snapshot: Snapshot) -> Mapping[str, Any]:
    raw_state = snapshot.raw_state if isinstance(snapshot.raw_state, Mapping) else {}
    state_type = str(raw_state.get("state_type", snapshot.state_type))
    compacted = _compact_mapping(raw_state, state_type=state_type, path=())
    compacted["state_type"] = state_type
    return compacted


def _compact_mapping(
    value: Mapping[str, Any],
    *,
    state_type: str,
    path: tuple[str, ...],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, child in value.items():
        if key in {"battle_log", "debug", "raw_markdown"}:
            continue

        if key in {"draw_pile", "discard_pile", "exhaust_pile"}:
            continue

        if child is None:
            continue

        if _should_drop_scalar_field(state_type, path, key):
            continue

        if isinstance(child, Mapping):
            compacted_child = _compact_mapping(child, state_type=state_type, path=(*path, key))
            if compacted_child:
                result[key] = compacted_child
            continue

        if isinstance(child, list):
            compacted_list = _compact_list(key, child, state_type=state_type, path=path)
            if compacted_list:
                result[key] = compacted_list
            continue

        result[key] = child
    return result


def _compact_list(
    key: str,
    items: list[Any],
    *,
    state_type: str,
    path: tuple[str, ...],
) -> list[Any]:
    limit = _list_limit_for_key(key)
    compacted: list[Any] = []
    for item in items[:limit]:
        if isinstance(item, Mapping):
            compacted_item = _compact_mapping(item, state_type=state_type, path=(*path, key))
            if compacted_item:
                compacted.append(compacted_item)
        elif isinstance(item, list):
            compacted_list = _compact_list(key, item, state_type=state_type, path=(*path, key))
            if compacted_list:
                compacted.append(compacted_list)
        else:
            compacted.append(item)
    return compacted


def _list_limit_for_key(key: str) -> int:
    if key == "hand":
        return 10
    if key == "enemies":
        return 6
    if key == "items":
        return 10
    if key == "relics":
        return 5
    if key == "status":
        return 8
    return 6


def _should_drop_scalar_field(state_type: str, path: tuple[str, ...], key: str) -> bool:
    if state_type not in {"monster", "elite", "boss"}:
        return False

    parent = path[-1] if path else ""
    if key == "keywords":
        return True
    if parent == "hand" and key == "id":
        return True
    if parent == "relics" and key in {"id", "counter"}:
        return True
    if parent == "enemies" and key == "combat_id":
        return True
    return False


def _parse_json_output(content: Any) -> Mapping[str, Any]:
    if isinstance(content, list):
        content = "".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )

    text = str(content).strip()
    if not text:
        raise RuntimeError("Provider returned empty content")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(f"Provider did not return JSON: {text}")
        parsed = json.loads(text[start:end + 1])

    if not isinstance(parsed, dict):
        raise RuntimeError("Provider returned non-object JSON")
    return parsed


def _parse_claude_cli_output(stdout: str) -> Mapping[str, Any]:
    payload = _parse_json_output(stdout)
    if any(key in payload for key in {"action", "title", "lines", "narration_title", "narration_lines"}):
        return payload

    for key in ("result", "text", "content", "message"):
        if key in payload:
            return _parse_json_output(payload[key])

    raise RuntimeError(f"Claude provider returned unexpected JSON envelope: {payload}")


def _normalize_lines(raw_lines: Any) -> tuple[str, ...]:
    if raw_lines is None:
        return ()
    if isinstance(raw_lines, str):
        return tuple(line.strip() for line in raw_lines.splitlines() if line.strip())
    if isinstance(raw_lines, list):
        return tuple(str(line).strip() for line in raw_lines if str(line).strip())
    return (str(raw_lines).strip(),) if str(raw_lines).strip() else ()


def _normalize_action_name(raw_action: Any) -> str:
    action = str(raw_action or "").strip()
    while len(action) >= 2 and action[0] == action[-1] and action[0] in {"'", '"', "`"}:
        action = action[1:-1].strip()
    return ACTION_ALIASES.get(action, action)


def _normalize_action_params(action: str, params: Mapping[str, Any]) -> dict[str, Any]:
    aliases = PARAM_ALIASES_BY_ACTION.get(action, {})
    normalized: dict[str, Any] = {}
    for key, value in params.items():
        canonical_key = aliases.get(str(key).strip(), str(key).strip())
        normalized[canonical_key] = value
    return normalized


def _build_parameter_hints_text(allowed_actions: tuple[str, ...] | None) -> str:
    if not allowed_actions:
        return ""

    hint_lines: list[str] = []
    for action in allowed_actions:
        for hint in ACTION_PARAMETER_HINTS.get(action, ()):
            hint_lines.append(f"- {action}: {hint}")

    if not hint_lines:
        return ""
    return "\nParameter hints:\n" + "\n".join(hint_lines) + "\n"


def _build_state_specific_constraints(snapshot: Snapshot) -> str:
    if snapshot.state_type != "event":
        return ""

    raw_state = snapshot.raw_state if isinstance(snapshot.raw_state, Mapping) else {}
    event_state = raw_state.get("event") if isinstance(raw_state.get("event"), Mapping) else raw_state
    in_dialogue = bool(event_state.get("in_dialogue")) if isinstance(event_state, Mapping) else False
    if in_dialogue:
        return (
            "\nEvent-specific rule:\n"
            "- This event is still in dialogue. Use advance_dialogue. Never use proceed on event screens.\n"
        )

    return (
        "\nEvent-specific rule:\n"
        "- Never use proceed on event screens. To continue an event, use choose_event_option with the correct option index.\n"
    )


def _anthropic_messages_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1/messages"):
        return normalized
    if normalized.endswith("/v1"):
        return normalized + "/messages"
    parsed = urlparse(normalized)
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if len(path_segments) > 1:
        return normalized
    return normalized + "/v1/messages"


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    try:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.communicate(timeout=1)
        except Exception:
            pass


ADVISE_SYSTEM_PROMPT = """Return only valid JSON.

You are a QQ-pet-style Slay the Spire 2 companion.
Reply in Simplified Chinese.
Speak in short, concrete guidance.
Do not explain the whole game.
Do not wrap JSON in markdown fences.
"""


AUTO_SYSTEM_PROMPT = """Return only valid JSON.

You are a Slay the Spire 2 auto-play companion.
Reply in Simplified Chinese.
Pick one legal next action for the current state.
Keep narration short and concrete.
Do not wrap JSON in markdown fences.
"""
