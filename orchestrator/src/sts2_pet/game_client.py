from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError, loads
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .models import Snapshot


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


class GameClient:
    def __init__(
        self,
        base_url: str,
        state_path: str = "/api/v1/singleplayer",
        action_path: str = "/api/v1/singleplayer",
        *,
        timeout_seconds: float = 5.0,
        transport: JsonTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._state_path = state_path
        self._action_path = action_path
        self._timeout_seconds = timeout_seconds
        self._transport = transport or StdlibJsonTransport()

    def get_state(self) -> Mapping[str, Any]:
        return self._transport.get_json(
            self._url(f"{self._state_path}?format=json"),
            self._timeout_seconds,
        )

    def post_action(self, action: str, **params: Any) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"action": action, **params}
        response = self._transport.post_json(self._url(self._action_path), payload, self._timeout_seconds)
        if str(response.get("status", "")).lower() != "ok":
            detail = str(
                response.get("message")
                or response.get("error")
                or "Unknown action failure"
            ).strip() or "Unknown action failure"
            raise RuntimeError(f"Action '{action}' failed: {detail}")
        return response

    def read_snapshot(self) -> Snapshot:
        payload = self.get_state()
        return Snapshot(state_type=str(payload.get("state_type", "unknown")))

    def send_action(self, action: str, **params: Any) -> Mapping[str, Any]:
        return self.post_action(action, **params)

    def _url(self, path: str) -> str:
        return urljoin(f"{self._base_url}/", path.lstrip("/"))
