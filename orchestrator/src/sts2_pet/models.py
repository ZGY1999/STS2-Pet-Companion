from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Mode(str, Enum):
    PAUSE = "pause"
    ADVISE = "advise"
    AUTO = "auto"


@dataclass(frozen=True, slots=True)
class Snapshot:
    state_type: str
    raw_state: Mapping[str, object] | None = None
