from __future__ import annotations

from typing import Any

import requests


DYNASTY_DADDY_PLAYER_VALUES_URL = (
    "https://dynasty-daddy.com/api/v1/player/all/today"
)
USER_AGENT = "ironbound-editorial-desk/0.1"


class RankingsClient:
    """Read-only client for external ranking inputs used by the editorial desk."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def dynasty_daddy_player_values(self) -> list[dict[str, Any]]:
        response = self.session.get(
            DYNASTY_DADDY_PLAYER_VALUES_URL,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Dynasty Daddy player response was not a list")
        return payload
