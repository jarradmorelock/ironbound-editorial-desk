from __future__ import annotations

from collections import defaultdict
from typing import Any

from .chronicle_queries import ChronicleQueries


_EPSILON = 0.001


def evidence_id(kind: str, season: str, week: int | None, *parts: object) -> str:
    tokens = [str(kind), str(season), str(week) if week is not None else "season"]
    tokens.extend(str(part) for part in parts)
    return ":".join(tokens)


def _publication_history(snapshot: dict[str, Any]) -> dict[str, Any]:
    return (
        snapshot.get("publication_sleeper")
        or snapshot.get("flagship_sleeper")
        or {}
    )


def _season(snapshot: dict[str, Any]) -> str:
    return str(
        (snapshot.get("nfl_state") or {}).get("season")
        or (snapshot.get("league") or {}).get("season")
        or ""
    )


def _league_key(snapshot: dict[str, Any]) -> str:
    return str((snapshot.get("editorial") or {}).get("league_key") or "")


def _expected_rosters(snapshot: dict[str, Any]) -> set[int]:
    return {
        int(row.get("roster_id") or 0)
        for row in snapshot.get("rosters") or []
        if int(row.get("roster_id") or 0) > 0
    }


def _team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    result: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        user = users.get(str(roster.get("owner_id"))) or {}
        metadata = user.get("metadata") or {}
        result[roster_id] = str(
            metadata.get("team_name")
            or user.get("display_name")
            or f"Roster {roster_id}"
        )
    return result


def _week_rows(snapshot: dict[str, Any], week: int) -> list[dict[str, Any]]:
    current_week = int(snapshot.get("week") or 0)
    if week == current_week:
        return [dict(row) for row in snapshot.get("matchups") or []]
    history = _publication_history(snapshot)
    weeks = ((history.get("schedule") or {}).get("weeks") or {})
    return [dict(row) for row in weeks.get(str(week)) or weeks.get(week) or []]


def _points_map(row: dict[str, Any]) -> dict[str, float]:
    raw = row.get("players_points_custom")
    if not isinstance(raw, dict) or not raw:
        raw = row.get("players_points")
    result: dict[str, float] = {}
    for player_id, value in (raw or {}).items():
        try:
            result[str(player_id)] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _pair_results(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        matchup_id = row.get("matchup_id")
        if matchup_id is None:
            continue
        grouped[str(matchup_id)].append(row)
    return [
        (pair[0], pair[1])
        for pair in grouped.values()
        if len(pair) == 2
    ]


def _record_before(
    canonical_by_week: dict[int, list[dict[str, Any]]],
    roster_ids: set[int],
    week: int,
) -> dict[str, dict[str, int]]:
    records = {
        roster_id: {"wins": 0, "losses": 0, "ties": 0}
        for roster_id in roster_ids
    }
    for prior_week in range(1, week):
        for left, right in _pair_results(canonical_by_week.get(prior_week, [])):
            left_id = int(left.get("roster_id") or 0)
            right_id = int(right.get("roster_id") or 0)
            left_points = float(left.get("points") or 0)
            right_points = float(right.get("points") or 0)
            if left_points > right_points:
                records[left_id]["wins"] += 1
                records[right_id]["losses"] += 1
            elif right_points > left_points:
                records[right_id]["wins"] += 1
                records[left_id]["losses"] += 1
            else:
                records[left_id]["ties"] += 1
                records[right_id]["ties"] += 1
    return {str(key): value for key, value in records.items()}


def _division_map(snapshot: dict[str, Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        settings = roster.get("settings") or {}
        division = settings.get("division")
        if roster_id and division not in (None, 0, "0", ""):
            result[roster_id] = str(division)
    return result


def _division_summary(
    snapshot: dict[str, Any],
    canonical_by_week: dict[int, list[dict[str, Any]]],
    through_week: int,
) -> dict[str, Any]:
    divisions = _division_map(snapshot)
    if not divisions:
        return {"status": "NOT_APPLICABLE", "divisions": {}}

    result: dict[str, dict[str, Any]] = {}
    for division in sorted(set(divisions.values())):
        result[division] = {
            "division": division,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "cross_division_wins": 0,
            "cross_division_losses": 0,
            "cross_division_ties": 0,
            "points_for": 0.0,
            "team_games": 0,
            "scoring_average": None,
        }

    for week in range(1, through_week + 1):
        rows = canonical_by_week.get(week, [])
        for row in rows:
            roster_id = int(row.get("roster_id") or 0)
            division = divisions.get(roster_id)
            if division is None:
                continue
            result[division]["points_for"] += float(row.get("points") or 0)
            result[division]["team_games"] += 1

        for left, right in _pair_results(rows):
            left_id = int(left.get("roster_id") or 0)
            right_id = int(right.get("roster_id") or 0)
            left_div = divisions.get(left_id)
            right_div = divisions.get(right_id)
            if left_div is None or right_div is None:
                continue
            lp = float(left.get("points") or 0)
            rp = float(right.get("points") or 0)
            if left_div == right_div:
                if lp > rp:
                    result[left_div]["wins"] += 1
                    result[left_div]["losses"] += 1
                elif rp > lp:
                    result[left_div]["wins"] += 1
                    result[left_div]["losses"] += 1
                else:
                    result[left_div]["ties"] += 2
            else:
                if lp > rp:
                    result[left_div]["cross_division_wins"] += 1
                    result[right_div]["cross_division_losses"] += 1
                elif rp > lp:
                    result[right_div]["cross_division_wins"] += 1
                    result[left_div]["cross_division_losses"] += 1
                else:
                    result[left_div]["cross_division_ties"] += 1
                    result[right_div]["cross_division_ties"] += 1

    for row in result.values():
        row["points_for"] = round(row["points_for"], 4)
        row["scoring_average"] = (
            round(row["points_for"] / row["team_games"], 4)
            if row["team_games"]
            else None
        )
    return {"status": "READY", "divisions": result}


def build_canonical_league_evidence(
    snapshot: dict[str, Any],
    chronicle: ChronicleQueries | None = None,
) -> dict[str, Any]:
    season = _season(snapshot)
    current_week = int(snapshot.get("week") or 0)
    league_key = _league_key(snapshot)
    roster_ids = _expected_rosters(snapshot)
    teams = _team_names(snapshot)

    chronicle_matchups: dict[tuple[int, int], dict[str, Any]] = {}
    chronicle_players: dict[tuple[int, int, str], dict[str, Any]] = {}
    if chronicle is not None:
        if hasattr(chronicle, "season_matchup_finals"):
            for row in chronicle.season_matchup_finals(league_key, season) or []:
                chronicle_matchups[(int(row.get("week") or 0), int(row.get("roster_id") or 0))] = dict(row)
        if hasattr(chronicle, "season_player_fantasy_finals"):
            for row in chronicle.season_player_fantasy_finals(league_key, season) or []:
                chronicle_players[
                    (
                        int(row.get("week") or 0),
                        int(row.get("roster_id") or 0),
                        str(row.get("player_id") or ""),
                    )
                ] = dict(row)

    canonical_by_week: dict[int, list[dict[str, Any]]] = {}
    player_weeks: list[dict[str, Any]] = []
    evidence_index: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    missing: list[str] = []

    for week in range(1, current_week + 1):
        rows = _week_rows(snapshot, week)
        by_roster = {
            int(row.get("roster_id") or 0): dict(row)
            for row in rows
            if int(row.get("roster_id") or 0)
        }

        for roster_id in sorted(roster_ids):
            sleeper_row = by_roster.get(roster_id)
            chronicle_row = chronicle_matchups.get((week, roster_id))
            if sleeper_row is None and chronicle_row is not None:
                sleeper_row = {
                    "matchup_id": chronicle_row.get("matchup_id"),
                    "roster_id": roster_id,
                    "points": chronicle_row.get("points"),
                    "players": [],
                    "starters": [],
                    "players_points": {},
                    "_authority": "chronicle",
                }
                by_roster[roster_id] = sleeper_row
            if sleeper_row is None:
                missing.append(f"week {week} roster {roster_id}")
                continue

            if chronicle_row is not None:
                try:
                    sleeper_points = float(sleeper_row.get("points") or 0)
                    chronicle_points = float(chronicle_row.get("points") or 0)
                except (TypeError, ValueError):
                    sleeper_points = chronicle_points = 0.0
                if abs(sleeper_points - chronicle_points) > _EPSILON:
                    conflicts.append(
                        {
                            "status": "MANUAL_VERIFY",
                            "kind": "MATCHUP_FINAL",
                            "week": week,
                            "roster_id": roster_id,
                            "sleeper": sleeper_points,
                            "chronicle": chronicle_points,
                        }
                    )

        canonical_rows: list[dict[str, Any]] = []
        for roster_id, row in sorted(by_roster.items()):
            if roster_id not in roster_ids:
                continue
            points = float(row.get("points") or 0)
            eid = evidence_id("team-week", season, week, roster_id)
            canonical = {
                "evidence_id": eid,
                "week": week,
                "matchup_id": row.get("matchup_id"),
                "roster_id": roster_id,
                "team": teams.get(roster_id, f"Roster {roster_id}"),
                "points": points,
                "starters": [str(x) for x in row.get("starters") or [] if str(x) != "0"],
                "players": [str(x) for x in row.get("players") or [] if str(x) != "0"],
                "authority": row.get("_authority") or "sleeper_matchups",
                "source_refs": [
                    ref for ref in [
                        chronicle_matchups.get((week, roster_id), {}).get("event_id")
                    ] if ref
                ],
            }
            canonical_rows.append(canonical)
            evidence_index[eid] = canonical

            sleeper_points_map = _points_map(row)
            player_ids = set(canonical["players"]) | set(canonical["starters"]) | set(sleeper_points_map)
            for player_id in sorted(player_ids):
                score = sleeper_points_map.get(player_id)
                chronicle_player = chronicle_players.get((week, roster_id, player_id))
                if score is None and chronicle_player is not None:
                    score = float(chronicle_player.get("points") or 0)
                if score is None:
                    continue
                if chronicle_player is not None and abs(float(score) - float(chronicle_player.get("points") or 0)) > _EPSILON:
                    conflicts.append(
                        {
                            "status": "MANUAL_VERIFY",
                            "kind": "PLAYER_FANTASY_WEEK_FINAL",
                            "week": week,
                            "roster_id": roster_id,
                            "player_id": player_id,
                            "sleeper": float(score),
                            "chronicle": float(chronicle_player.get("points") or 0),
                        }
                    )
                peid = evidence_id("player-week", season, week, roster_id, player_id)
                prow = {
                    "evidence_id": peid,
                    "week": week,
                    "roster_id": roster_id,
                    "team": teams.get(roster_id, f"Roster {roster_id}"),
                    "player_id": player_id,
                    "points": float(score),
                    "started": player_id in canonical["starters"],
                    "authority": "sleeper_matchups" if player_id in sleeper_points_map else "chronicle",
                }
                player_weeks.append(prow)
                evidence_index[peid] = prow
        canonical_by_week[week] = canonical_rows

    if conflicts:
        coverage_status = "MANUAL_VERIFY"
        reason = f"{len(conflicts)} authoritative source conflict(s) require review."
    elif missing:
        coverage_status = "PARTIAL"
        reason = "Missing historical matchup coverage: " + ", ".join(missing)
    else:
        coverage_status = "READY"
        reason = None

    entering_records = {
        str(week): _record_before(canonical_by_week, roster_ids, week)
        for week in range(1, current_week + 1)
    }

    team_totals: dict[str, dict[str, Any]] = {}
    player_totals: dict[str, dict[str, Any]] = {}
    totals_available = coverage_status == "READY"
    if totals_available:
        team_accumulator: dict[int, float] = defaultdict(float)
        for rows in canonical_by_week.values():
            for row in rows:
                team_accumulator[int(row["roster_id"])] += float(row["points"])
        team_totals = {
            str(roster_id): {
                "roster_id": roster_id,
                "team": teams.get(roster_id, f"Roster {roster_id}"),
                "points": round(points, 4),
                "through_week": current_week,
            }
            for roster_id, points in sorted(team_accumulator.items())
        }

        player_accumulator: dict[str, float] = defaultdict(float)
        player_roster: dict[str, int] = {}
        for row in player_weeks:
            player_accumulator[row["player_id"]] += float(row["points"])
            player_roster[row["player_id"]] = int(row["roster_id"])
        player_totals = {
            player_id: {
                "player_id": player_id,
                "roster_id": player_roster.get(player_id),
                "team": teams.get(player_roster.get(player_id, 0)),
                "points": round(points, 4),
                "through_week": current_week,
            }
            for player_id, points in sorted(player_accumulator.items())
        }

    return {
        "schema_version": 1,
        "league_key": league_key,
        "season": season,
        "through_week": current_week,
        "coverage": {
            "status": coverage_status,
            "weeks": list(range(1, current_week + 1)),
            "reason": reason,
            "missing": missing,
        },
        "historical_matchups": [
            row for week in range(1, current_week + 1) for row in canonical_by_week.get(week, [])
        ],
        "player_weeks": player_weeks,
        "entering_records": entering_records,
        "team_season_totals": team_totals,
        "team_season_totals_status": "READY" if totals_available else "UNAVAILABLE",
        "player_season_totals": player_totals,
        "player_season_totals_status": "READY" if totals_available else "UNAVAILABLE",
        "division_summary": (
            _division_summary(snapshot, canonical_by_week, current_week)
            if totals_available
            else {"status": "UNAVAILABLE", "divisions": {}, "reason": reason}
        ),
        "evidence_index": evidence_index,
        "conflicts": conflicts,
    }
