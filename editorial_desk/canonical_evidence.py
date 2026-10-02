from __future__ import annotations

from collections import defaultdict
from typing import Any


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evidence_id(
    kind: str,
    season: str,
    week: int | None,
    *parts: object,
) -> str:
    suffix = ":".join(str(value) for value in parts if value not in (None, ""))
    middle = str(week) if week is not None else "season"
    base = f"{str(kind).casefold()}:{season}:{middle}"
    return f"{base}:{suffix}" if suffix else base


def _history_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    return (
        snapshot.get("publication_sleeper")
        or snapshot.get("flagship_sleeper")
        or {}
    )


def _team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {
        str(row.get("user_id") or ""): row
        for row in snapshot.get("users") or []
    }
    names: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        if not roster_id:
            continue
        owner = users.get(str(roster.get("owner_id") or "")) or {}
        metadata = owner.get("metadata") or {}
        names[roster_id] = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
    return names


def _player_name(snapshot: dict[str, Any], player_id: str) -> str:
    row = (snapshot.get("players") or {}).get(str(player_id)) or {}
    return str(row.get("full_name") or row.get("name") or player_id)


def _player_position(snapshot: dict[str, Any], player_id: str) -> str | None:
    row = (snapshot.get("players") or {}).get(str(player_id)) or {}
    value = row.get("position")
    return str(value) if value else None


def _points_map(matchup: dict[str, Any]) -> dict[str, float]:
    raw = (
        matchup.get("players_points_custom")
        or matchup.get("players_points")
        or {}
    )
    return {
        str(player_id): float(value or 0)
        for player_id, value in raw.items()
        if player_id is not None
    }


def _status_for_totals(
    *,
    conflicts: list[dict[str, Any]],
    incomplete_weeks: list[int],
) -> str:
    if conflicts:
        return "MANUAL_VERIFY"
    if incomplete_weeks:
        return "UNAVAILABLE"
    return "READY"


def _build_division_summary(
    snapshot: dict[str, Any],
    matchups: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    roster_division = {
        int(row.get("roster_id") or 0): (row.get("settings") or {}).get("division")
        for row in snapshot.get("rosters") or []
        if int(row.get("roster_id") or 0)
    }
    roster_division = {
        roster_id: int(division_id)
        for roster_id, division_id in roster_division.items()
        if division_id not in (None, "", 0, "0")
    }
    if not roster_division:
        return {}

    metadata = (snapshot.get("league") or {}).get("metadata") or {}
    result: dict[str, dict[str, Any]] = {}
    for division_id in sorted(set(roster_division.values())):
        key = str(division_id)
        result[key] = {
            "division_id": division_id,
            "division": str(
                metadata.get(f"division_{division_id}")
                or f"Division {division_id}"
            ),
            "points": 0.0,
            "team_games": 0,
            "average_points": 0.0,
            "internal_wins": 0,
            "internal_losses": 0,
            "internal_ties": 0,
            "cross_division_wins": 0,
            "cross_division_losses": 0,
            "cross_division_ties": 0,
        }

    grouped: dict[tuple[int, object], list[dict[str, Any]]] = defaultdict(list)
    for row in matchups:
        roster_id = int(row.get("roster_id") or 0)
        division_id = roster_division.get(roster_id)
        if division_id is None:
            continue
        key = str(division_id)
        points = _number(row.get("points"))
        if points is not None:
            result[key]["points"] += points
            result[key]["team_games"] += 1
        grouped[(int(row.get("week") or 0), row.get("matchup_id"))].append(row)

    for (_, matchup_id), sides in grouped.items():
        if matchup_id is None or len(sides) != 2:
            continue
        left, right = sides
        left_id = int(left.get("roster_id") or 0)
        right_id = int(right.get("roster_id") or 0)
        left_div = roster_division.get(left_id)
        right_div = roster_division.get(right_id)
        if left_div is None or right_div is None:
            continue
        left_points = _number(left.get("points"))
        right_points = _number(right.get("points"))
        if left_points is None or right_points is None:
            continue

        same = left_div == right_div
        left_bucket = result[str(left_div)]
        right_bucket = result[str(right_div)]
        prefix = "internal" if same else "cross_division"
        if left_points > right_points:
            left_bucket[f"{prefix}_wins"] += 1
            right_bucket[f"{prefix}_losses"] += 1
        elif left_points < right_points:
            left_bucket[f"{prefix}_losses"] += 1
            right_bucket[f"{prefix}_wins"] += 1
        else:
            left_bucket[f"{prefix}_ties"] += 1
            right_bucket[f"{prefix}_ties"] += 1

    for row in result.values():
        row["points"] = round(float(row["points"]), 4)
        games = int(row["team_games"])
        row["average_points"] = (
            round(float(row["points"]) / games, 4) if games else 0.0
        )
    return result


def build_canonical_league_evidence(
    snapshot: dict[str, Any],
    chronicle: Any | None = None,
) -> dict[str, Any]:
    """Reconcile historical Sleeper league facts into one publication-facing view.

    Sleeper's exact week matchups are primary evidence for league results,
    submitted lineups, and player fantasy scores. Chronicle corroborates those
    facts and fills gaps when Sleeper history is genuinely absent. Conflicting
    finalized values are never silently reconciled.
    """

    season = str(
        (snapshot.get("league") or {}).get("season")
        or (snapshot.get("nfl_state") or {}).get("season")
        or ""
    )
    through_week = int(snapshot.get("week") or 0)
    league_key = str((snapshot.get("editorial") or {}).get("league_key") or "")
    team_names = _team_names(snapshot)
    expected_rosters = {
        int(row.get("roster_id") or 0)
        for row in snapshot.get("rosters") or []
        if int(row.get("roster_id") or 0)
    }

    context = _history_context(snapshot)
    schedule = (context.get("schedule") or {}).get("weeks") or {}

    by_week_roster: dict[tuple[int, int], dict[str, Any]] = {}
    by_week_player: dict[tuple[int, int, str], dict[str, Any]] = {}
    evidence_index: dict[str, dict[str, Any]] = {}

    def add_matchup_row(
        row: dict[str, Any],
        *,
        week: int,
        source: str,
        replace: bool = False,
    ) -> None:
        roster_id = int(row.get("roster_id") or 0)
        if not roster_id or not (0 < week <= through_week):
            return
        points = _number(row.get("points"))
        if points is None:
            return
        key = (week, roster_id)
        value = {
            "season": season,
            "week": week,
            "matchup_id": row.get("matchup_id"),
            "roster_id": roster_id,
            "team": team_names.get(roster_id, f"Roster {roster_id}"),
            "points": round(points, 4),
            "starters": [
                str(player_id)
                for player_id in row.get("starters") or []
                if str(player_id) != "0"
            ],
            "players": [
                str(player_id)
                for player_id in row.get("players") or []
                if str(player_id) != "0"
            ],
            "source": source,
        }
        if replace or key not in by_week_roster:
            by_week_roster[key] = value
        eid = evidence_id("MATCHUP_FINAL", season, week, roster_id)
        evidence_index[eid] = {
            "evidence_id": eid,
            "fact_type": "MATCHUP_FINAL",
            "season": season,
            "week": week,
            "roster_id": roster_id,
            "authority": source,
            "status": "VERIFIED",
        }

        points_map = _points_map(row)
        player_ids = (
            value["players"]
            or list(points_map)
        )
        for player_id in player_ids:
            if player_id not in points_map:
                continue
            pkey = (week, roster_id, player_id)
            pvalue = {
                "season": season,
                "week": week,
                "roster_id": roster_id,
                "player_id": player_id,
                "player": _player_name(snapshot, player_id),
                "position": _player_position(snapshot, player_id),
                "points": round(points_map[player_id], 4),
                "started": player_id in value["starters"],
                "source": source,
            }
            if replace or pkey not in by_week_player:
                by_week_player[pkey] = pvalue
            peid = evidence_id(
                "PLAYER_FANTASY_WEEK_FINAL",
                season,
                week,
                roster_id,
                player_id,
            )
            evidence_index[peid] = {
                "evidence_id": peid,
                "fact_type": "PLAYER_FANTASY_WEEK_FINAL",
                "season": season,
                "week": week,
                "roster_id": roster_id,
                "player_id": player_id,
                "authority": source,
                "status": "VERIFIED",
            }

    for raw_week, rows in schedule.items():
        try:
            week = int(raw_week)
        except (TypeError, ValueError):
            continue
        if not (0 < week <= through_week):
            continue
        for row in rows or []:
            if isinstance(row, dict):
                add_matchup_row(row, week=week, source="sleeper_matchups")

    # The reviewed-week snapshot is the freshest exact Sleeper matchup payload.
    for row in snapshot.get("matchups") or []:
        if isinstance(row, dict):
            add_matchup_row(
                row,
                week=through_week,
                source="sleeper_matchups",
                replace=True,
            )

    conflicts: list[dict[str, Any]] = []

    if chronicle is not None and hasattr(chronicle, "season_matchup_finals"):
        for row in chronicle.season_matchup_finals(league_key, season):
            week = int(row.get("week") or 0)
            roster_id = int(row.get("roster_id") or 0)
            if not (0 < week <= through_week and roster_id):
                continue
            key = (week, roster_id)
            chrono_points = _number(row.get("points"))
            sleeper = by_week_roster.get(key)
            if sleeper is not None and chrono_points is not None:
                if abs(float(sleeper["points"]) - chrono_points) > 0.001:
                    conflicts.append(
                        {
                            "status": "MANUAL_VERIFY",
                            "kind": "MATCHUP_FINAL",
                            "season": season,
                            "week": week,
                            "roster_id": roster_id,
                            "sleeper_value": float(sleeper["points"]),
                            "chronicle_value": chrono_points,
                            "chronicle_event_id": row.get("event_id"),
                        }
                    )
                continue
            if chrono_points is not None:
                add_matchup_row(
                    {
                        "roster_id": roster_id,
                        "matchup_id": row.get("matchup_id"),
                        "points": chrono_points,
                    },
                    week=week,
                    source="chronicle_matchup_final",
                )

    if chronicle is not None and hasattr(
        chronicle, "season_player_fantasy_finals"
    ):
        for row in chronicle.season_player_fantasy_finals(
            league_key, season
        ):
            week = int(row.get("week") or 0)
            roster_id = int(row.get("roster_id") or 0)
            player_id = str(row.get("player_id") or "")
            points = _number(row.get("points"))
            if not (
                0 < week <= through_week
                and roster_id
                and player_id
                and points is not None
            ):
                continue
            key = (week, roster_id, player_id)
            sleeper = by_week_player.get(key)
            if sleeper is not None:
                if abs(float(sleeper["points"]) - points) > 0.001:
                    conflicts.append(
                        {
                            "status": "MANUAL_VERIFY",
                            "kind": "PLAYER_FANTASY_WEEK_FINAL",
                            "season": season,
                            "week": week,
                            "roster_id": roster_id,
                            "player_id": player_id,
                            "sleeper_value": float(sleeper["points"]),
                            "chronicle_value": points,
                            "chronicle_event_id": row.get("event_id"),
                        }
                    )
                continue
            by_week_player[key] = {
                "season": season,
                "week": week,
                "roster_id": roster_id,
                "player_id": player_id,
                "player": _player_name(snapshot, player_id),
                "position": row.get("position")
                or _player_position(snapshot, player_id),
                "points": round(points, 4),
                "started": None,
                "source": "chronicle_player_fantasy_final",
            }

    week_rosters: dict[int, set[int]] = defaultdict(set)
    for week, roster_id in by_week_roster:
        week_rosters[week].add(roster_id)

    incomplete_weeks = [
        week
        for week in range(1, through_week + 1)
        if expected_rosters
        and not expected_rosters.issubset(week_rosters.get(week, set()))
    ]
    missing_by_week = {
        str(week): sorted(expected_rosters - week_rosters.get(week, set()))
        for week in incomplete_weeks
    }

    coverage_status = (
        "MANUAL_VERIFY"
        if conflicts
        else "PARTIAL"
        if incomplete_weeks
        else "READY"
    )

    entering_records: dict[str, dict[str, dict[str, int]]] = {}
    running = {
        roster_id: {"wins": 0, "losses": 0, "ties": 0}
        for roster_id in expected_rosters
    }
    for week in range(1, through_week + 1):
        entering_records[str(week)] = {
            str(roster_id): dict(record)
            for roster_id, record in running.items()
        }
        grouped: dict[object, list[dict[str, Any]]] = defaultdict(list)
        for (row_week, _), row in by_week_roster.items():
            if row_week == week:
                grouped[row.get("matchup_id")].append(row)
        for matchup_id, sides in grouped.items():
            if matchup_id is None or len(sides) != 2:
                continue
            left, right = sides
            left_id = int(left["roster_id"])
            right_id = int(right["roster_id"])
            left_points = float(left["points"])
            right_points = float(right["points"])
            if left_points > right_points:
                running[left_id]["wins"] += 1
                running[right_id]["losses"] += 1
            elif left_points < right_points:
                running[left_id]["losses"] += 1
                running[right_id]["wins"] += 1
            else:
                running[left_id]["ties"] += 1
                running[right_id]["ties"] += 1

    team_totals: dict[str, dict[str, Any]] = {}
    for (_, roster_id), row in sorted(by_week_roster.items()):
        key = str(roster_id)
        target = team_totals.setdefault(
            key,
            {
                "roster_id": roster_id,
                "team": team_names.get(roster_id, f"Roster {roster_id}"),
                "points": 0.0,
                "weeks": 0,
                "through_week": through_week,
            },
        )
        target["points"] += float(row["points"])
        target["weeks"] += 1
    for row in team_totals.values():
        row["points"] = round(float(row["points"]), 4)

    player_totals: dict[str, dict[str, Any]] = {}
    for (_, roster_id, player_id), row in sorted(by_week_player.items()):
        target = player_totals.setdefault(
            player_id,
            {
                "player_id": player_id,
                "player": row.get("player")
                or _player_name(snapshot, player_id),
                "position": row.get("position")
                or _player_position(snapshot, player_id),
                "points": 0.0,
                "weeks": 0,
                "through_week": through_week,
                "roster_ids": set(),
            },
        )
        target["points"] += float(row["points"])
        target["weeks"] += 1
        target["roster_ids"].add(roster_id)
    for row in player_totals.values():
        row["points"] = round(float(row["points"]), 4)
        row["roster_ids"] = sorted(row["roster_ids"])

    historical_matchups = [
        dict(row)
        for _, row in sorted(by_week_roster.items())
    ]
    player_weeks = [
        dict(row)
        for _, row in sorted(by_week_player.items())
    ]

    totals_status = _status_for_totals(
        conflicts=conflicts,
        incomplete_weeks=incomplete_weeks,
    )

    return {
        "schema_version": 1,
        "season": season,
        "through_week": through_week,
        "coverage": {
            "status": coverage_status,
            "weeks": sorted(week_rosters),
            "incomplete_weeks": incomplete_weeks,
            "missing_rosters_by_week": missing_by_week,
            "expected_rosters": sorted(expected_rosters),
            "source_status": (context.get("schedule") or {}).get("status"),
        },
        "historical_matchups": historical_matchups,
        "player_weeks": player_weeks,
        "entering_records": entering_records,
        "team_season_totals_status": totals_status,
        "team_season_totals": team_totals,
        "player_season_totals_status": totals_status,
        "player_season_totals": player_totals,
        "division_summary": _build_division_summary(
            snapshot, historical_matchups
        ),
        "evidence_index": evidence_index,
        "conflicts": conflicts,
    }
