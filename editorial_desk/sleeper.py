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
        self._players_cache: dict[str, Any] | None = None

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
        if self._players_cache is None:
            payload = self.get_json("players/nfl")
            if not isinstance(payload, dict):
                raise ValueError("Sleeper player directory response was not an object")
            self._players_cache = payload
        return self._players_cache

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

    def drafts(self, league_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"league/{league_id}/drafts")

    def draft_picks(self, draft_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"draft/{draft_id}/picks")

    def draft_traded_picks(self, draft_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"draft/{draft_id}/traded_picks")

    def winners_bracket(self, league_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"league/{league_id}/winners_bracket")

    def losers_bracket(self, league_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"league/{league_id}/losers_bracket")

    def projections(self, season: str, week: int) -> dict[str, Any]:
        payload = self.get_json(f"projections/nfl/regular/{season}/{week}")
        if not isinstance(payload, dict):
            raise ValueError("Sleeper projection response was not an object")
        return payload
