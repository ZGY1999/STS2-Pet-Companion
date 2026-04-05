from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sts2_pet.game_client import GameClient
from sts2_pet.models import Mode
from sts2_pet.pet_client import PetClient, PetMessage
from sts2_pet.provider import AdviceBubble


class FakeTransport:
    def __init__(
        self,
        get_payloads: list[dict[str, object]] | None = None,
        *,
        post_payloads: list[dict[str, object]] | None = None,
    ) -> None:
        self.get_payloads = list(get_payloads or [])
        self.post_payloads = list(post_payloads or [])
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def get_json(self, url: str, timeout_seconds: float) -> dict[str, object]:
        self.calls.append(("GET", url, None))
        return self.get_payloads.pop(0)

    def post_json(self, url: str, payload: dict[str, object], timeout_seconds: float) -> dict[str, object]:
        self.calls.append(("POST", url, payload))
        if self.post_payloads:
            return self.post_payloads.pop(0)
        return {"status": "ok"}


def test_game_client_reads_snapshot_and_posts_action() -> None:
    transport = FakeTransport([{"state_type": "monster"}])
    client = GameClient(
        "http://example.test",
        transport=transport,
    )

    state = client.get_state()
    response = client.post_action("end_turn", target="front")

    assert state == {"state_type": "monster"}
    assert response == {"status": "ok"}
    assert transport.calls == [
        ("GET", "http://example.test/api/v1/singleplayer?format=json", None),
        ("POST", "http://example.test/api/v1/singleplayer", {"action": "end_turn", "target": "front"}),
    ]


def test_game_client_raises_when_action_api_reports_error() -> None:
    transport = FakeTransport(
        [],
        post_payloads=[{"status": "error", "message": "No proceed button available or enabled"}],
    )
    client = GameClient("http://example.test", transport=transport)

    try:
        client.post_action("proceed")
    except RuntimeError as error:
        message = str(error)
        assert "proceed" in message
        assert "No proceed button available or enabled" in message
    else:
        raise AssertionError("Expected action API failure to raise")


def test_game_client_raises_when_action_api_reports_error_field() -> None:
    transport = FakeTransport(
        [],
        post_payloads=[{"status": "error", "error": "Map node index 1 out of range (1 options available)"}],
    )
    client = GameClient("http://example.test", transport=transport)

    try:
        client.post_action("choose_map_node", index=1)
    except RuntimeError as error:
        message = str(error)
        assert "choose_map_node" in message
        assert "Map node index 1 out of range" in message
    else:
        raise AssertionError("Expected action API failure to raise")


def test_game_client_reads_error_field_when_action_api_reports_error() -> None:
    transport = FakeTransport(
        [],
        post_payloads=[{"status": "error", "error": "Map node index 2 out of range (1 options available)"}],
    )
    client = GameClient("http://example.test", transport=transport)

    try:
        client.post_action("choose_map_node", index=2)
    except RuntimeError as error:
        message = str(error)
        assert "choose_map_node" in message
        assert "Map node index 2 out of range" in message
    else:
        raise AssertionError("Expected action API failure to raise")


def test_pet_client_reads_status_sets_mode_and_pushes_bubble() -> None:
    transport = FakeTransport([{"mode": "auto"}])
    client = PetClient("http://example.test", transport=transport)

    status = client.get_status()
    mode_response = client.set_mode(Mode.AUTO)
    response = client.set_message(
        PetMessage(mode=Mode.AUTO, state="auto_running", title="Go", lines=("Line 1",))
    )

    assert status == {"mode": "auto"}
    assert mode_response == {"status": "ok"}
    assert response == {"status": "ok"}
    assert transport.calls == [
        ("GET", "http://example.test/api/v1/pet/status", None),
        (
            "POST",
            "http://example.test/api/v1/pet/mode",
            {"mode": "auto"},
        ),
        (
            "POST",
            "http://example.test/api/v1/pet/message",
            {"mode": "auto", "state": "auto_running", "title": "Go", "lines": ["Line 1"]},
        ),
    ]


def test_pet_client_accepts_advice_bubble_payload() -> None:
    transport = FakeTransport([{"mode": "advise"}])
    client = PetClient("http://example.test", transport=transport)

    response = client.set_message(AdviceBubble(title="Plan", lines=("Look left", "Then act")))

    assert response == {"status": "ok"}
    assert transport.calls[0] == ("POST", "http://example.test/api/v1/pet/message", {
        "mode": "advise",
        "state": "talking",
        "title": "Plan",
        "lines": ["Look left", "Then act"],
    })


def test_pet_client_reads_status_from_pet_status_path() -> None:
    transport = FakeTransport([{"mode": "pause", "state": "paused"}])
    client = PetClient("http://example.test", transport=transport)

    status = client.get_status()

    assert status == {"mode": "pause", "state": "paused"}
    assert transport.calls == [("GET", "http://example.test/api/v1/pet/status", None)]
