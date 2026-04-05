from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError, loads
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .models import Mode
from .provider import AdviceBubble


class JsonTransport(Protocol):
    def get_json(self, url: str, timeout_seconds: float) -> Mapping[str, Any]: ...

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class StdlibJsonTransport:
    def get_json(self, url: str, timeout_seconds: float) -> Mapping[str, Any]:
        request = Request(url, method="GET")
        return self._read_json(request, timeout_seconds)

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        body = _encode_json(payload)
        request = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._read_json(request, timeout_seconds)

    def _read_json(self, request: Request, timeout_seconds: float) -> Mapping[str, Any]:
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {error.code}: {body}") from error

        try:
            parsed = loads(raw)
        except JSONDecodeError as error:
            raise RuntimeError(f"Invalid JSON response: {raw}") from error

        if not isinstance(parsed, dict):
            raise RuntimeError("Expected a JSON object response")
        return parsed


def _encode_json(payload: Mapping[str, Any]) -> bytes:
    from json import dumps

    return dumps(payload, ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True, slots=True)
class PetMessage:
    mode: Mode
    state: str
    title: str
    lines: tuple[str, ...] = ()


class PetClient:
    def __init__(
        self,
        base_url: str,
        status_path: str = "/api/v1/pet/status",
        mode_path: str = "/api/v1/pet/mode",
        message_path: str = "/api/v1/pet/message",
        *,
        timeout_seconds: float = 5.0,
        transport: JsonTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._status_path = status_path
        self._mode_path = mode_path
        self._message_path = message_path
        self._timeout_seconds = timeout_seconds
        self._transport = transport or StdlibJsonTransport()

    def get_status(self) -> Mapping[str, Any]:
        return self._transport.get_json(self._url(self._status_path), self._timeout_seconds)

    def set_mode(self, mode: Mode | str) -> Mapping[str, Any]:
        mode_value = mode.value if isinstance(mode, Mode) else str(mode)
        return self._transport.post_json(
            self._url(self._mode_path),
            {"mode": mode_value},
            self._timeout_seconds,
        )

    def set_message(self, message: PetMessage | AdviceBubble) -> Mapping[str, Any]:
        if isinstance(message, AdviceBubble):
            payload: dict[str, Any] = {
                "mode": Mode.ADVISE.value,
                "state": "talking",
                "title": message.title,
                "lines": list(message.lines),
            }
        else:
            payload = {
                "mode": message.mode.value,
                "state": message.state,
                "title": message.title,
                "lines": list(message.lines),
            }
        return self._transport.post_json(self._url(self._message_path), payload, self._timeout_seconds)

    def read_status(self) -> Mapping[str, Any]:
        return self.get_status()

    def read_mode(self) -> Mode:
        payload = self.get_status()
        return self._mode_from_payload(payload)

    def push_bubble(self, message: PetMessage | AdviceBubble) -> Mapping[str, Any]:
        return self.set_message(message)

    @staticmethod
    def _mode_from_payload(payload: Mapping[str, Any]) -> Mode:
        raw_mode = payload.get("mode", payload.get("state", Mode.PAUSE.value))
        try:
            return Mode(str(raw_mode))
        except ValueError:
            return Mode.PAUSE

    def _url(self, path: str) -> str:
        return urljoin(f"{self._base_url}/", path.lstrip("/"))
