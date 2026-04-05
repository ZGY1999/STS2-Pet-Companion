from .models import Mode, Snapshot

ADVICE_STATES = {
    "monster",
    "elite",
    "boss",
    "card_reward",
    "map",
    "shop",
    "event",
    "rest_site",
    "relic_select",
}


def should_generate_advice(mode: Mode, snapshot: Snapshot) -> bool:
    return mode is Mode.ADVISE and snapshot.state_type in ADVICE_STATES
