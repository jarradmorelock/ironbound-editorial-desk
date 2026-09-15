from __future__ import annotations

import csv
import gzip
import io
from typing import Any, Iterator

import requests


SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "schedules/games.csv.gz"
)
PLAYER_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv"
)
PLAY_BY_PLAY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "pbp/play_by_play_{season}.csv.gz"
)
SNAP_COUNTS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "snap_counts/snap_counts_{season}.csv"
)
USER_AGENT = "ironbound-editorial-desk/0.1"


class NFLVerseClient:
    """Read the public nflverse releases used for NFL game context."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self._raw_cache: dict[str, bytes] = {}

    def schedule(self, season: str, week: int) -> list[dict[str, Any]]:
        return [
            row for row in self.season_schedule(season) if row["week"] == week
        ]

    def season_schedule(self, season: str) -> list[dict[str, Any]]:
        rows = self._csv_rows(SCHEDULE_URL, compressed=True)
        return [
            {
                "game_id": row.get("game_id"),
                "season": _integer(row.get("season")),
                "week": _integer(row.get("week")),
                "game_type": row.get("game_type"),
                "gameday": row.get("gameday"),
                "weekday": row.get("weekday"),
                "gametime": row.get("gametime"),
                "away_team": row.get("away_team"),
                "away_score": _integer_or_none(row.get("away_score")),
                "home_team": row.get("home_team"),
                "home_score": _integer_or_none(row.get("home_score")),
                "overtime": _integer(row.get("overtime")),
            }
            for row in rows
            if row.get("season") == str(season)
            and row.get("game_type") == "REG"
        ]

    def player_stats(self, season: str, week: int) -> list[dict[str, Any]]:
        rows = self._csv_rows(
            PLAYER_STATS_URL.format(season=season), compressed=False
        )
        fields = (
            "player_id",
            "player_name",
            "player_display_name",
            "position",
            "game_id",
            "team",
            "opponent_team",
            "completions",
            "attempts",
            "passing_yards",
            "passing_tds",
            "passing_interceptions",
            "passing_first_downs",
            "passing_2pt_conversions",
            "carries",
            "rushing_yards",
            "rushing_tds",
            "rushing_first_downs",
            "rushing_2pt_conversions",
            "receptions",
            "targets",
            "receiving_yards",
            "receiving_tds",
            "receiving_first_downs",
            "receiving_2pt_conversions",
            "fumbles",
            "fumbles_lost_total",
            "special_teams_tds",
            "def_tackles_solo",
            "def_tackle_assists",
            "def_sacks",
            "def_interceptions",
            "def_tds",
            "fg_made",
            "fg_att",
            "fg_long",
            "pat_made",
            "pat_att",
            "fantasy_points",
            "fantasy_points_ppr",
        )
        text_fields = {
            "player_id",
            "player_name",
            "player_display_name",
            "position",
            "game_id",
            "team",
            "opponent_team",
        }
        return [
            {
                field: (
                    row.get(field)
                    if field in text_fields
                    else _number(row.get(field))
                )
                for field in fields
            }
            for row in rows
            if row.get("season") == str(season)
            and row.get("week") == str(week)
            and row.get("season_type") == "REG"
        ]

    def snap_counts(self, season: str, week: int) -> list[dict[str, Any]]:
        rows = self._csv_rows(
            SNAP_COUNTS_URL.format(season=season), compressed=False
        )
        return [
            {
                "game_id": row.get("game_id"),
                "player": row.get("player"),
                "pfr_player_id": row.get("pfr_player_id"),
                "position": row.get("position"),
                "team": row.get("team"),
                "opponent": row.get("opponent"),
                "offense_snaps": _number(row.get("offense_snaps")),
                "offense_pct": _number(row.get("offense_pct")),
            }
            for row in rows
            if row.get("season") == str(season)
            and row.get("week") == str(week)
            and row.get("game_type") == "REG"
        ]

    def play_by_play(self, season: str, week: int) -> list[dict[str, Any]]:
        """Return a compact Week-N play feed for usage/game-script analysis."""
        rows = self._csv_rows(
            PLAY_BY_PLAY_URL.format(season=season), compressed=True
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            if row.get("season") != str(season) or row.get("week") != str(week):
                continue
            if row.get("season_type") not in (None, "", "REG"):
                continue
            results.append(
                {
                    "game_id": row.get("game_id"),
                    "quarter": _integer(row.get("qtr")),
                    "clock": row.get("time"),
                    "game_seconds_remaining": _integer(
                        row.get("game_seconds_remaining")
                    ),
                    "posteam": row.get("posteam"),
                    "defteam": row.get("defteam"),
                    "down": _integer_or_none(row.get("down")),
                    "ydstogo": _number(row.get("ydstogo")),
                    "yardline_100": _number(row.get("yardline_100")),
                    "play_type": row.get("play_type"),
                    "pass_attempt": _truthy(row.get("pass_attempt")),
                    "rush_attempt": _truthy(row.get("rush_attempt")),
                    "complete_pass": _truthy(row.get("complete_pass")),
                    "pass_touchdown": _truthy(row.get("pass_touchdown")),
                    "rush_touchdown": _truthy(row.get("rush_touchdown")),
                    "touchdown": _truthy(row.get("touchdown")),
                    "interception": _truthy(row.get("interception")),
                    "passer_player_id": row.get("passer_player_id"),
                    "receiver_player_id": row.get("receiver_player_id"),
                    "rusher_player_id": row.get("rusher_player_id"),
                    "td_player_id": row.get("td_player_id"),
                    "yards_gained": _number(row.get("yards_gained")),
                    "first_down": _truthy(row.get("first_down")),
                    "first_down_rush": _truthy(row.get("first_down_rush")),
                    "first_down_pass": _truthy(row.get("first_down_pass")),
                    "qb_kneel": _truthy(row.get("qb_kneel")),
                    "qb_spike": _truthy(row.get("qb_spike")),
                    "score_differential": _number(row.get("score_differential")),
                    "posteam_score_post": _number(row.get("posteam_score_post")),
                    "defteam_score_post": _number(row.get("defteam_score_post")),
                    "description": str(row.get("desc") or "").strip(),
                }
            )
        return results

    def noteworthy_late_plays(
        self, season: str, week: int
    ) -> list[dict[str, Any]]:
        rows = self._csv_rows(
            PLAY_BY_PLAY_URL.format(season=season), compressed=True
        )
        results = []
        for row in rows:
            if row.get("season") != str(season) or row.get("week") != str(week):
                continue
            quarter = _integer(row.get("qtr"))
            seconds = _integer(row.get("game_seconds_remaining"))
            late = quarter >= 5 or (quarter == 4 and seconds <= 300)
            touchdown = _truthy(row.get("touchdown"))
            field_goal = row.get("field_goal_result") == "made"
            two_point = row.get("two_point_conv_result") == "success"
            safety = _truthy(row.get("safety"))
            yards = _number(row.get("yards_gained"))
            big_play = yards >= 40
            if not late or not (
                touchdown or field_goal or two_point or safety or big_play
            ):
                continue
            description = str(row.get("desc") or "").strip()
            if not description:
                continue
            player_ids = sorted(
                {
                    str(row.get(field))
                    for field in (
                        "td_player_id",
                        "passer_player_id",
                        "receiver_player_id",
                        "rusher_player_id",
                        "kicker_player_id",
                        "fantasy_player_id",
                    )
                    if row.get(field)
                }
            )
            results.append(
                {
                    "play_id": row.get("play_id"),
                    "game_id": row.get("game_id"),
                    "quarter": quarter,
                    "clock": row.get("time"),
                    "game_seconds_remaining": seconds,
                    "description": description,
                    "play_type": row.get("play_type"),
                    "yards_gained": yards,
                    "touchdown": touchdown,
                    "field_goal": field_goal,
                    "two_point_conversion": two_point,
                    "safety": safety,
                    "walkoff_candidate": quarter >= 5
                    or (
                        seconds <= 15
                        and (touchdown or field_goal or two_point or safety)
                    ),
                    "player_ids": player_ids,
                    "home_score_after": _integer(row.get("total_home_score")),
                    "away_score_after": _integer(row.get("total_away_score")),
                }
            )
        return results

    def _csv_rows(
        self, url: str, compressed: bool
    ) -> Iterator[dict[str, str]]:
        if url not in self._raw_cache:
            response = self.session.get(
                url,
                headers={"Accept": "text/csv", "User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            self._raw_cache[url] = response.content
        raw = io.BytesIO(self._raw_cache[url])
        binary = gzip.GzipFile(fileobj=raw) if compressed else raw
        with io.TextIOWrapper(binary, encoding="utf-8", newline="") as stream:
            yield from csv.DictReader(stream)


def _integer(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _integer_or_none(value: Any) -> int | None:
    if value in (None, "", "NA"):
        return None
    return _integer(value)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _truthy(value: Any) -> bool:
    return str(value or "").casefold() in {"1", "true", "yes"}
