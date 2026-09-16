from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .chronicle_events import ChronicleEvent, make_event
from .chronicle_identity import IdentityRegistry


@dataclass(frozen=True)
class HeadToHeadSeries:
    identity_a: str
    identity_b: str
    wins_a: int
    wins_b: int
    ties: int
    games: int
    playoff_games: int
    current_streak_identity: str | None
    current_streak_length: int


@dataclass(frozen=True)
class MaterializedLeagueHistory:
    league_key: str
    head_to_head: dict[tuple[str, str], HeadToHeadSeries]
    matchups: tuple[dict[str, Any], ...]
    records: dict[str, dict[str, Any]]
    seasons: dict[str, dict[str, Any]]
    transactions: tuple[dict[str, Any], ...]
    record_events: tuple[ChronicleEvent, ...]
    coverage_start_season: str | None
    coverage_complete: bool
    coverage_warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "league_key": self.league_key,
            "head_to_head": [
                asdict(self.head_to_head[key]) for key in sorted(self.head_to_head)
            ],
            "matchups": list(self.matchups),
            "records": self.records,
            "seasons": self.seasons,
            "transactions": list(self.transactions),
            "record_events": [event.to_dict() for event in self.record_events],
            "coverage": {
                "start_season": self.coverage_start_season,
                "complete": self.coverage_complete,
                "warnings": list(self.coverage_warnings),
            },
        }


def _field(event: ChronicleEvent | dict[str, Any], name: str, default: Any = None) -> Any:
    if isinstance(event, dict):
        return event.get(name, default)
    return getattr(event, name, default)


def effective_events(
    events: Iterable[ChronicleEvent | dict[str, Any]],
) -> list[ChronicleEvent | dict[str, Any]]:
    rows = list(events)
    superseded = {
        str(_field(event, "correction_of"))
        for event in rows
        if _field(event, "correction_of")
    }
    return [
        event
        for event in rows
        if str(_field(event, "event_id")) not in superseded
    ]


def _season_sort(value: str) -> tuple[int, str]:
    try:
        return (0, f"{int(value):08d}")
    except (TypeError, ValueError):
        return (1, str(value))


def _event_sort_key(event: ChronicleEvent | dict[str, Any]) -> tuple[Any, ...]:
    season = str(_field(event, "season") or "")
    week = _field(event, "week")
    return (
        _season_sort(season),
        int(week) if week is not None else 99,
        str(_field(event, "occurred_at") or ""),
        str(_field(event, "event_id") or ""),
    )


def materialize_league(
    events: Iterable[ChronicleEvent | dict[str, Any]],
    registry: IdentityRegistry,
    *,
    coverage_warnings: Iterable[str] = (),
) -> MaterializedLeagueHistory:
    effective = sorted(effective_events(events), key=_event_sort_key)
    league_keys = {
        str(_field(event, "league_key"))
        for event in effective
        if _field(event, "league_key") is not None
    }
    if len(league_keys) > 1:
        raise ValueError("materialize_league accepts events from exactly one league")
    league_key = next(iter(league_keys), "unknown")

    matchup_rows: list[dict[str, Any]] = []
    record_totals: dict[str, dict[str, Any]] = {}
    season_totals: dict[str, dict[str, Any]] = {}
    h2h_games: dict[tuple[str, str], list[dict[str, Any]]] = {}
    transaction_rows: list[dict[str, Any]] = []
    record_events: list[ChronicleEvent] = []
    all_time_high_score: float | None = None
    all_time_largest_margin: float | None = None

    transaction_types = {
        "TRADE",
        "WAIVER_ADD",
        "FREE_AGENT_ADD",
        "DROP",
        "TRADED_PICK",
        "DRAFT_PICK",
    }

    for event in effective:
        event_type = str(_field(event, "event_type") or "")
        if event_type in transaction_types:
            transaction_rows.append(_event_summary(event))

        if event_type == "PLAYOFF_BRACKET_RESULT":
            _apply_explicit_winners_bracket_placement(
                event,
                league_key=league_key,
                registry=registry,
                season_totals=season_totals,
            )
            continue

        if event_type != "MATCHUP_FINAL":
            continue

        season = str(_field(event, "season") or "unknown")
        week = int(_field(event, "week") or 0)
        evidence = dict(_field(event, "evidence") or {})
        sides = evidence.get("rosters") or []
        if len(sides) != 2:
            continue
        left_raw, right_raw = sides
        left_id = registry.competitor_for(
            league_key, season, int(left_raw["roster_id"])
        )
        right_id = registry.competitor_for(
            league_key, season, int(right_raw["roster_id"])
        )
        left_points = float(left_raw.get("points") or 0)
        right_points = float(right_raw.get("points") or 0)
        competition = str(evidence.get("competition") or "regular_season")
        if left_points > right_points:
            winner, loser = left_id, right_id
        elif right_points > left_points:
            winner, loser = right_id, left_id
        else:
            winner = loser = None
        margin = abs(left_points - right_points)
        row = {
            "event_id": str(_field(event, "event_id")),
            "season": season,
            "week": week,
            "matchup_id": evidence.get("matchup_id"),
            "competition": competition,
            "left_identity": left_id,
            "left_roster_id": int(left_raw["roster_id"]),
            "left_points": left_points,
            "right_identity": right_id,
            "right_roster_id": int(right_raw["roster_id"]),
            "right_points": right_points,
            "winner_identity": winner,
            "loser_identity": loser,
            "margin": margin,
            "tie": winner is None,
        }
        matchup_rows.append(row)
        pair = tuple(sorted((left_id, right_id)))
        h2h_games.setdefault(pair, []).append(row)

        for identity, points_for, points_against in (
            (left_id, left_points, right_points),
            (right_id, right_points, left_points),
        ):
            total = record_totals.setdefault(identity, _empty_record())
            season_key = f"{season}:{identity}"
            season_total = season_totals.setdefault(season_key, _empty_record())
            for target in (total, season_total):
                target["games"] += 1
                target["points_for"] += points_for
                target["points_against"] += points_against
                if winner is None:
                    target["ties"] += 1
                elif identity == winner:
                    target["wins"] += 1
                    if competition == "playoffs":
                        target["playoff_wins"] += 1
                else:
                    target["losses"] += 1
                    if competition == "playoffs":
                        target["playoff_losses"] += 1
            season_total["season"] = season
            season_total["identity"] = identity

            if all_time_high_score is None or points_for > all_time_high_score:
                record_events.append(
                    _record_event(
                        league_key=league_key,
                        season=season,
                        week=week,
                        matchup_event_id=row["event_id"],
                        record_type="all_time_team_high_score",
                        value=points_for,
                        previous_value=all_time_high_score,
                        identity=identity,
                    )
                )
                all_time_high_score = points_for

        if all_time_largest_margin is None or margin > all_time_largest_margin:
            record_events.append(
                _record_event(
                    league_key=league_key,
                    season=season,
                    week=week,
                    matchup_event_id=row["event_id"],
                    record_type="all_time_largest_margin",
                    value=margin,
                    previous_value=all_time_largest_margin,
                    identity=winner,
                )
            )
            all_time_largest_margin = margin

    head_to_head = {
        pair: _series_from_games(pair, games)
        for pair, games in sorted(h2h_games.items())
    }
    warnings = tuple(str(item) for item in coverage_warnings)
    seasons = {
        key: _rounded_record(value)
        for key, value in sorted(season_totals.items())
    }
    records = {
        key: _rounded_record(value)
        for key, value in sorted(record_totals.items())
    }
    covered_seasons = sorted(
        {
            str(row.get("season"))
            for row in seasons.values()
            if row.get("season") is not None
        }
        | {row["season"] for row in matchup_rows},
        key=_season_sort,
    )
    return MaterializedLeagueHistory(
        league_key=league_key,
        head_to_head=head_to_head,
        matchups=tuple(matchup_rows),
        records=records,
        seasons=seasons,
        transactions=tuple(transaction_rows),
        record_events=tuple(record_events),
        coverage_start_season=covered_seasons[0] if covered_seasons else None,
        coverage_complete=not warnings,
        coverage_warnings=warnings,
    )


def _apply_explicit_winners_bracket_placement(
    event: ChronicleEvent | dict[str, Any],
    *,
    league_key: str,
    registry: IdentityRegistry,
    season_totals: dict[str, dict[str, Any]],
) -> None:
    entities = dict(_field(event, "entities") or {})
    if str(entities.get("bracket") or "").casefold() != "winners":
        return
    evidence = dict(_field(event, "evidence") or {})
    placement = evidence.get("p")
    winner_roster = evidence.get("w")
    loser_roster = evidence.get("l")
    if placement is None or winner_roster is None or loser_roster is None:
        return
    try:
        placement = int(placement)
        winner_roster = int(winner_roster)
        loser_roster = int(loser_roster)
    except (TypeError, ValueError):
        return
    if placement < 1:
        return

    season = str(_field(event, "season") or "unknown")
    winner_identity = registry.competitor_for(
        league_key, season, winner_roster
    )
    loser_identity = registry.competitor_for(
        league_key, season, loser_roster
    )
    for identity, finish in (
        (winner_identity, placement),
        (loser_identity, placement + 1),
    ):
        season_key = f"{season}:{identity}"
        season_total = season_totals.setdefault(season_key, _empty_record())
        season_total["season"] = season
        season_total["identity"] = identity
        season_total["finish"] = finish
        season_total["champion"] = finish == 1


def _empty_record() -> dict[str, Any]:
    return {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "ties": 0,
        "points_for": 0.0,
        "points_against": 0.0,
        "playoff_wins": 0,
        "playoff_losses": 0,
    }


def _rounded_record(value: dict[str, Any]) -> dict[str, Any]:
    row = dict(value)
    row["points_for"] = round(float(row.get("points_for") or 0), 2)
    row["points_against"] = round(float(row.get("points_against") or 0), 2)
    return row


def _series_from_games(
    pair: tuple[str, str], games: list[dict[str, Any]]
) -> HeadToHeadSeries:
    a, b = pair
    wins_a = sum(1 for row in games if row["winner_identity"] == a)
    wins_b = sum(1 for row in games if row["winner_identity"] == b)
    ties = sum(1 for row in games if row["winner_identity"] is None)
    playoff_games = sum(1 for row in games if row["competition"] == "playoffs")
    streak_identity: str | None = None
    streak_length = 0
    for row in games:
        winner = row["winner_identity"]
        if winner is None:
            streak_identity = None
            streak_length = 0
        elif winner == streak_identity:
            streak_length += 1
        else:
            streak_identity = winner
            streak_length = 1
    return HeadToHeadSeries(
        identity_a=a,
        identity_b=b,
        wins_a=wins_a,
        wins_b=wins_b,
        ties=ties,
        games=len(games),
        playoff_games=playoff_games,
        current_streak_identity=streak_identity,
        current_streak_length=streak_length,
    )


def _record_event(
    *,
    league_key: str,
    season: str,
    week: int,
    matchup_event_id: str,
    record_type: str,
    value: float,
    previous_value: float | None,
    identity: str | None,
) -> ChronicleEvent:
    return make_event(
        event_type="RECORD_SET",
        source="chronicle_materializer",
        source_ref=(
            f"record:{league_key}:{record_type}:{matchup_event_id}:"
            f"{identity or 'league'}"
        ),
        league_key=league_key,
        season=season,
        week=week,
        provenance="reconstructed_from_sleeper",
        entities={"identity": identity} if identity else {},
        observed_at=f"materialized:{season}:week:{week}",
        evidence={
            "record_type": record_type,
            "value": round(float(value), 2),
            "previous_value": (
                round(float(previous_value), 2)
                if previous_value is not None
                else None
            ),
            "matchup_event_id": matchup_event_id,
        },
    )


def _event_summary(event: ChronicleEvent | dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(_field(event, "event_id") or ""),
        "event_type": str(_field(event, "event_type") or ""),
        "season": str(_field(event, "season") or ""),
        "week": _field(event, "week"),
        "occurred_at": _field(event, "occurred_at"),
        "entities": dict(_field(event, "entities") or {}),
        "evidence": dict(_field(event, "evidence") or {}),
    }
