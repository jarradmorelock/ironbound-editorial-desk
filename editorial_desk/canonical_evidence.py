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


def _current_roster_by_player(snapshot: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        if not roster_id:
            continue
        for field in ("players", "taxi", "reserve"):
            for player_id in roster.get(field) or []:
                result[str(player_id)] = roster_id
    return result


def _transaction_additions(snapshot: dict[str, Any]) -> dict[str, int]:
    history = _publication_history(snapshot)
    weeks = ((history.get("transactions") or {}).get("weeks") or {})
    acquired: dict[str, int] = {}
    for raw_week, transactions in weeks.items():
        try:
            week = int(raw_week)
        except (TypeError, ValueError):
            continue
        for transaction in transactions or []:
            if transaction.get("status") not in {None, "complete"}:
                continue
            additions = dict(transaction.get("adds") or {})
            received = ((transaction.get("players") or {}).get("received_by") or {})
            for roster_name, rows in received.items():
                for row in rows or []:
                    player_id = str(row.get("player_id") or row.get("player") or "")
                    roster_id = row.get("roster_id")
                    if player_id and roster_id is not None:
                        additions[player_id] = roster_id
            for player_id, roster_id in additions.items():
                acquired[str(player_id)] = min(acquired.get(str(player_id), week), week)
    return acquired


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
    """Build writer-ready team and division records through the reviewed week."""
    divisions = _division_map(snapshot)
    if not divisions:
        return {
            "status": "NOT_APPLICABLE",
            "divisions": {},
            "team_records": {},
        }

    teams = _team_names(snapshot)
    metadata = (snapshot.get("league") or {}).get("metadata") or {}

    def empty_record() -> dict[str, int]:
        return {"wins": 0, "losses": 0, "ties": 0}

    def apply_result(record: dict[str, int], mine: float, other: float) -> None:
        if mine > other:
            record["wins"] += 1
        elif mine < other:
            record["losses"] += 1
        else:
            record["ties"] += 1

    result: dict[str, dict[str, Any]] = {}
    for division in sorted(set(divisions.values())):
        result[division] = {
            "division": division,
            "division_name": str(
                metadata.get(f"division_{division}") or f"Division {division}"
            ),
            # Backward-compatible pooled internal fields.
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "cross_division_wins": 0,
            "cross_division_losses": 0,
            "cross_division_ties": 0,
            "points_for": 0.0,
            "team_games": 0,
            "scoring_average": None,
            "teams": [],
            "evidence_ids": [],
        }

    team_records: dict[str, dict[str, Any]] = {}
    for roster_id, division in sorted(divisions.items()):
        team_records[str(roster_id)] = {
            "roster_id": roster_id,
            "team": teams.get(roster_id, f"Roster {roster_id}"),
            "division": division,
            "division_name": str(
                metadata.get(f"division_{division}") or f"Division {division}"
            ),
            "overall_record": empty_record(),
            "division_record": empty_record(),
            "cross_division_record": empty_record(),
            "points_for": 0.0,
            "team_games": 0,
            "scoring_average": None,
            "evidence_ids": [],
        }

    division_evidence: dict[str, set[str]] = defaultdict(set)

    for week in range(1, through_week + 1):
        rows = canonical_by_week.get(week, [])
        for row in rows:
            roster_id = int(row.get("roster_id") or 0)
            division = divisions.get(roster_id)
            team_row = team_records.get(str(roster_id))
            if division is None or team_row is None:
                continue
            points = float(row.get("points") or 0)
            result[division]["points_for"] += points
            result[division]["team_games"] += 1
            team_row["points_for"] += points
            team_row["team_games"] += 1
            if row.get("evidence_id"):
                evidence = str(row["evidence_id"])
                team_row["evidence_ids"].append(evidence)
                division_evidence[division].add(evidence)

        for left, right in _pair_results(rows):
            left_id = int(left.get("roster_id") or 0)
            right_id = int(right.get("roster_id") or 0)
            left_div = divisions.get(left_id)
            right_div = divisions.get(right_id)
            left_team = team_records.get(str(left_id))
            right_team = team_records.get(str(right_id))
            if (
                left_div is None
                or right_div is None
                or left_team is None
                or right_team is None
            ):
                continue

            lp = float(left.get("points") or 0)
            rp = float(right.get("points") or 0)
            apply_result(left_team["overall_record"], lp, rp)
            apply_result(right_team["overall_record"], rp, lp)

            if left_div == right_div:
                apply_result(left_team["division_record"], lp, rp)
                apply_result(right_team["division_record"], rp, lp)
                if lp > rp:
                    result[left_div]["wins"] += 1
                    result[left_div]["losses"] += 1
                elif rp > lp:
                    result[left_div]["wins"] += 1
                    result[left_div]["losses"] += 1
                else:
                    result[left_div]["ties"] += 2
            else:
                apply_result(left_team["cross_division_record"], lp, rp)
                apply_result(right_team["cross_division_record"], rp, lp)
                if lp > rp:
                    result[left_div]["cross_division_wins"] += 1
                    result[right_div]["cross_division_losses"] += 1
                elif rp > lp:
                    result[right_div]["cross_division_wins"] += 1
                    result[left_div]["cross_division_losses"] += 1
                else:
                    result[left_div]["cross_division_ties"] += 1
                    result[right_div]["cross_division_ties"] += 1

    for team_row in team_records.values():
        team_row["points_for"] = round(float(team_row["points_for"]), 4)
        team_row["scoring_average"] = (
            round(team_row["points_for"] / team_row["team_games"], 4)
            if team_row["team_games"]
            else None
        )
        team_row["evidence_ids"] = sorted(set(team_row["evidence_ids"]))
        result[team_row["division"]]["teams"].append(team_row)

    for division, row in result.items():
        row["points_for"] = round(float(row["points_for"]), 4)
        row["scoring_average"] = (
            round(row["points_for"] / row["team_games"], 4)
            if row["team_games"]
            else None
        )
        row["pooled_internal_record"] = {
            "wins": row["wins"],
            "losses": row["losses"],
            "ties": row["ties"],
        }
        row["cross_division_record"] = {
            "wins": row["cross_division_wins"],
            "losses": row["cross_division_losses"],
            "ties": row["cross_division_ties"],
        }
        row["teams"].sort(key=lambda team: int(team["roster_id"]))
        row["evidence_ids"] = sorted(division_evidence.get(division, set()))

    return {
        "status": "READY",
        "through_week": through_week,
        "divisions": result,
        "team_records": team_records,
    }


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
            chronicle_ids = {
                player_id
                for (chronicle_week, chronicle_roster, player_id) in chronicle_players
                if chronicle_week == week and chronicle_roster == roster_id
            }
            player_ids = (
                set(canonical["players"])
                | set(canonical["starters"])
                | set(sleeper_points_map)
                | chronicle_ids
            )
            for player_id in sorted(player_ids):
                score = sleeper_points_map.get(player_id)
                chronicle_player = chronicle_players.get((week, roster_id, player_id))
                score_status = "OBSERVED" if player_id in sleeper_points_map else None
                authority = "sleeper_matchups" if player_id in sleeper_points_map else None
                if score is None and chronicle_player is not None:
                    score = float(chronicle_player.get("points") or 0)
                    score_status = chronicle_player.get("score_status") or (
                        "OBSERVED" if score else "CERTIFIED_ZERO"
                    )
                    authority = "chronicle"
                if score is None and player_id in set(canonical["players"]) | set(canonical["starters"]):
                    score = 0.0
                    score_status = "CERTIFIED_ZERO"
                    authority = "sleeper_matchups"
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
                    "score_status": score_status,
                    "membership_status": "ROSTERED",
                    "authority": authority,
                    "source_refs": [
                        ref
                        for ref in [
                            chronicle_player.get("event_id") if chronicle_player else None,
                            chronicle_player.get("source_ref") if chronicle_player else None,
                        ]
                        if ref
                    ],
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

    current_roster_by_player = _current_roster_by_player(snapshot)
    acquired_week = _transaction_additions(snapshot)
    player_week_coverage = {
        "observed": [],
        "certified_zero": [],
        "excluded": [],
        "unknown": [],
        "manual_verify": [],
    }
    for row in player_weeks:
        key = f"week {row['week']}:{row['player_id']}"
        if row.get("score_status") == "CERTIFIED_ZERO":
            player_week_coverage["certified_zero"].append(key)
        else:
            player_week_coverage["observed"].append(key)
    for conflict in conflicts:
        if conflict.get("kind") == "PLAYER_FANTASY_WEEK_FINAL":
            player_week_coverage["manual_verify"].append(
                f"week {conflict.get('week')}:{conflict.get('player_id')}"
            )
    for player_id in sorted(current_roster_by_player):
        for week in range(1, current_week + 1):
            if any(
                int(row.get("week") or 0) == week and row.get("player_id") == player_id
                for row in player_weeks
            ):
                continue
            acquired = acquired_week.get(player_id, 1)
            key = f"week {week}:{player_id}"
            if week < acquired:
                player_week_coverage["excluded"].append(key)
            else:
                player_week_coverage["unknown"].append(key)
    for values in player_week_coverage.values():
        values.sort()

    player_history_ready = not (
        player_week_coverage["unknown"] or player_week_coverage["manual_verify"]
    )

    entering_records = {
        str(week): _record_before(canonical_by_week, roster_ids, week)
        for week in range(1, current_week + 1)
    }

    team_totals: dict[str, dict[str, Any]] = {}
    player_totals: dict[str, dict[str, Any]] = {}
    totals_available = coverage_status == "READY"
    player_totals_available = totals_available and player_history_ready
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
    if not player_totals_available:
        player_totals = {}

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
        "player_week_coverage": player_week_coverage,
        "entering_records": entering_records,
        "team_season_totals": team_totals,
        "team_season_totals_status": "READY" if totals_available else "UNAVAILABLE",
        "player_season_totals": player_totals,
        "player_season_totals_status": "READY" if player_totals_available else "UNAVAILABLE",
        "division_summary": (
            _division_summary(snapshot, canonical_by_week, current_week)
            if totals_available
            else {"status": "UNAVAILABLE", "divisions": {}, "reason": reason}
        ),
        "evidence_index": evidence_index,
        "conflicts": conflicts,
    }
