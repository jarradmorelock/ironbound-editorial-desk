from __future__ import annotations

from typing import Any

import requests


BASE_URL = "https://api.sleeper.app/v1"
USER_AGENT = "ironbound-editorial-desk/0.1"


class SleeperClient:
    """Small read-only client for the public Sleeper API."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def get_json(self, path: str) -> Any:
        response = self.session.get(
            f"{BASE_URL}/{path.lstrip('/')}",
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def nfl_state(self) -> dict[str, Any]:
        return self.get_json("state/nfl")

    def players(self) -> dict[str, Any]:
        return self.get_json("players/nfl")

    def league(self, league_id: str) -> dict[str, Any]:
        return self.get_json(f"league/{league_id}")

    def users(self, league_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"league/{league_id}/users")

    def rosters(self, league_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"league/{league_id}/rosters")

    def matchups(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return self.get_json(f"league/{league_id}/matchups/{week}")

    def transactions(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return self.get_json(f"league/{league_id}/transactions/{week}")

    def traded_picks(self, league_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"league/{league_id}/traded_picks")
