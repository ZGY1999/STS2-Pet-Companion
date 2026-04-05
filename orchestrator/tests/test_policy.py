from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sts2_pet.models import Mode, Snapshot
from sts2_pet.policy import should_generate_advice


def test_pause_mode_never_generates_advice() -> None:
    snapshot = Snapshot(state_type="monster")

    assert should_generate_advice(Mode.PAUSE, snapshot) is False


def test_advise_mode_triggers_on_reward_choice() -> None:
    snapshot = Snapshot(state_type="card_reward")

    assert should_generate_advice(Mode.ADVISE, snapshot) is True


def test_advise_mode_rejects_unsupported_state() -> None:
    snapshot = Snapshot(state_type="unknown")

    assert should_generate_advice(Mode.ADVISE, snapshot) is False


def test_auto_mode_never_generates_advice() -> None:
    snapshot = Snapshot(state_type="card_reward")

    assert should_generate_advice(Mode.AUTO, snapshot) is False
