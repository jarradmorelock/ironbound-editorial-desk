from __future__ import annotations

from collections import defaultdict
from typing import Any

import requests

from .nflverse import NFLVerseClient
from .sleeper import SleeperClient


class PeriodDetectionError(RuntimeError):
    """Raised when the scheduled job cannot identify a safe completed week."""


def detect_completed_period(
    sleeper: SleeperClient | None = None,
    nflverse: NFLVerseClient | None = None,
) -> dict[str, Any]:
    sleeper = sleeper or SleeperClient()
    nflverse = nflverse or NFLVerseClient()
    try:
        state = sleeper.nfl_state()
        season = str(state.get("season") or "")
        state_week = int(state.get("week") or 0)
        season_type = str(state.get("season_type") or "").casefold()
        if not season or state_week < 1:
            raise PeriodDetectionError("Sleeper did not return an active NFL week")
        if season_type != "regular":
            return {
                "active": False,
                "season": season,
                "week": 0,
                "reason": f"Sleeper season type is {season_type or 'unknown'}",
            }

        schedule = nflverse.season_schedule(season)
    except (requests.RequestException, ValueError, KeyError, OSError) as exc:
        raise PeriodDetectionError(
            f"Could not read the NFL state and schedule: {exc}"
        ) from exc

    weeks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for game in schedule:
        week = int(game.get("week") or 0)
        if 1 <= week <= 18:
            weeks[week].append(game)
    completed = [
        week
        for week, games in weeks.items()
        if week <= state_week
        and games
        and all(
            game.get("away_score") is not None
            and game.get("home_score") is not None
            for game in games
        )
    ]
    if not completed:
        return {
            "active": False,
            "season": season,
            "week": 0,
            "reason": "No NFL week is fully complete yet",
        }
    week = max(completed)
    return {
        "active": True,
        "season": season,
        "week": week,
        "reason": f"NFL Week {week} is fully complete",
    }
