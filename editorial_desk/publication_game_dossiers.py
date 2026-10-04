from __future__ import annotations

from typing import Any


_NON_STARTER_SLOTS = {"BN", "IR", "RESERVE", "TAXI"}


def _team_directory(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    teams: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        if roster_id <= 0:
            continue
        user = users.get(str(roster.get("owner_id"))) or {}
        metadata = user.get("metadata") or {}
        teams[roster_id] = str(
            metadata.get("team_name")
            or user.get("display_name")
            or user.get("username")
            or f"Roster {roster_id}"
        )
    return teams


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


def _projection_rows(snapshot: dict[str, Any]) -> tuple[dict[str, float], str | None]:
    try:
        from .honors import frozen_projections

        player_points, _, error = frozen_projections(snapshot)
    except (ImportError, TypeError, ValueError):
        return {}, "Verified same-week player projections were unavailable."
    return {
        str(player_id): float(value)
        for player_id, value in (player_points or {}).items()
        if value is not None
    }, error


def _stat_rows_by_player(dossier: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stat_book = ((dossier.get("nfl_game_intelligence") or {}).get("stat_book") or {})
    rows = stat_book.get("rostered_records") or stat_book.get("records") or []
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        player_id = str(
            row.get("sleeper_player_id")
            or row.get("fantasy_player_id")
            or row.get("player_id")
            or ""
        )
        if player_id:
            result[player_id] = dict(row)
    return result


def _timing_by_matchup(dossier: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    timing = dossier.get("game_timing") or {}
    result: dict[str, list[dict[str, Any]]] = {}
    for lane in ("early_week", "thursday", "monday"):
        for row in (timing.get(lane) or {}).get("matchups") or []:
            matchup_id = row.get("matchup_id")
            if matchup_id is None:
                continue
            result.setdefault(str(matchup_id), []).append(
                {"lane": lane, **dict(row)}
            )
    return result


def add_health_evidence_ids(
    health: dict[str, Any],
    *,
    season: str,
    week: int,
) -> dict[str, Any]:
    result = dict(health or {})
    news_by_player: dict[str, list[dict[str, Any]]] = {}
    for event in result.get("news_events") or []:
        for linked in event.get("league_players") or []:
            player_id = str(linked.get("sleeper_player_id") or "")
            if player_id:
                news_by_player.setdefault(player_id, []).append(dict(event))

    rows = []
    for row in result.get("players") or []:
        item = dict(row)
        player_id = str(item.get("player_id") or item.get("player") or "unknown")
        observed = str(
            item.get("observed_at")
            or result.get("information_cutoff")
            or "unknown"
        )
        item.setdefault(
            "evidence_id",
            f"health-status:{season}:{week}:{player_id}:{observed}",
        )
        item["news_events"] = news_by_player.get(player_id, [])
        item["news_evidence_ids"] = [
            str(event.get("event_id"))
            for event in item["news_events"]
            if event.get("event_id")
        ]
        rows.append(item)
    result["players"] = rows
    return result


def build_flagship_game_dossiers(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    research: dict[str, Any],
    canonical: dict[str, Any],
    transactions: dict[str, Any],
    health: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compile all reviewed-week matchup facts needed by an offline writer."""
    week = int(research.get("week") or snapshot.get("week") or 0)
    teams = _team_directory(snapshot)
    players = snapshot.get("players") or {}
    rosters = {
        int(row.get("roster_id") or 0): row
        for row in snapshot.get("rosters") or []
        if int(row.get("roster_id") or 0) > 0
    }

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot.get("matchups") or []:
        matchup_id = row.get("matchup_id")
        if matchup_id is not None:
            groups.setdefault(str(matchup_id), []).append(dict(row))

    projections, projection_error = _projection_rows(snapshot)
    stats = _stat_rows_by_player(dossier)
    timing = _timing_by_matchup(dossier)
    entering = (canonical.get("entering_records") or {}).get(str(week)) or {}

    team_evidence = {
        int(row.get("roster_id") or 0): str(row.get("evidence_id") or "")
        for row in canonical.get("historical_matchups") or []
        if int(row.get("week") or 0) == week and row.get("evidence_id")
    }
    player_evidence = {
        (int(row.get("roster_id") or 0), str(row.get("player_id") or "")): str(
            row.get("evidence_id") or ""
        )
        for row in canonical.get("player_weeks") or []
        if int(row.get("week") or 0) == week
        and row.get("player_id")
        and row.get("evidence_id")
    }

    ranking_rows = (research.get("power_rankings_chart") or {}).get("rows") or []
    ranking_by_roster = {
        int(row.get("roster_id") or 0): dict(row)
        for row in ranking_rows
        if row.get("roster_id") is not None
    }
    ranking_by_team = {
        str(row.get("team") or "").strip().casefold(): dict(row)
        for row in ranking_rows
        if row.get("team")
    }

    health_by_roster: dict[int, list[dict[str, Any]]] = {}
    health_by_team: dict[str, list[dict[str, Any]]] = {}
    for row in health.get("players") or []:
        item = dict(row)
        try:
            health_by_roster.setdefault(int(item.get("roster_id")), []).append(item)
        except (TypeError, ValueError):
            pass
        team = str(item.get("fantasy_team") or item.get("team") or "").strip().casefold()
        if team:
            health_by_team.setdefault(team, []).append(item)

    transaction_rows = transactions.get("transactions") or []
    expected_slots = [
        str(slot)
        for slot in (snapshot.get("league") or {}).get("roster_positions") or []
        if str(slot) not in _NON_STARTER_SLOTS
    ]

    results: list[dict[str, Any]] = []
    for base in (research.get("game_coverage") or {}).get("games") or []:
        matchup_id = base.get("matchup_id")
        sides = groups.get(str(matchup_id), [])
        base_teams = {
            int(row.get("roster_id") or 0): dict(row)
            for row in base.get("teams") or []
            if int(row.get("roster_id") or 0) > 0
        }
        game_evidence: set[str] = set()
        compiled_teams: list[dict[str, Any]] = []

        for side in sorted(sides, key=lambda row: int(row.get("roster_id") or 0)):
            roster_id = int(side.get("roster_id") or 0)
            roster = rosters.get(roster_id) or {}
            team_name = str(
                teams.get(roster_id)
                or (base_teams.get(roster_id) or {}).get("team")
                or f"Roster {roster_id}"
            )
            point_map = _points_map(side)
            starters = [
                str(player_id)
                for player_id in side.get("starters") or []
                if str(player_id) != "0"
            ]
            excluded = {
                str(player_id)
                for key in ("reserve", "taxi")
                for player_id in roster.get(key) or []
            }
            active = [
                str(player_id)
                for player_id in (side.get("players") or roster.get("players") or [])
                if str(player_id) != "0"
            ]
            bench = [
                player_id
                for player_id in active
                if player_id not in set(starters) and player_id not in excluded
            ]

            def player_row(player_id: str, *, started: bool) -> dict[str, Any]:
                player = players.get(player_id) or {}
                stat = stats.get(player_id) or {}
                eid = player_evidence.get((roster_id, player_id))
                if eid:
                    game_evidence.add(eid)
                return {
                    "player_id": player_id,
                    "player": str(
                        player.get("full_name") or player.get("name") or player_id
                    ),
                    "position": player.get("position"),
                    "nfl_team": player.get("team"),
                    "started": started,
                    "fantasy_points": point_map.get(player_id),
                    "projected_points": projections.get(player_id),
                    "nfl_stat_line": stat.get("nfl_stat_line"),
                    "snap_share": stat.get("snap_share"),
                    "target_share": stat.get("target_share"),
                    "carry_share": stat.get("carry_share"),
                    "red_zone_opportunities": stat.get("red_zone_opportunities"),
                    "inside_10_opportunities": stat.get("inside_10_opportunities"),
                    "inside_5_opportunities": stat.get("inside_5_opportunities"),
                    "evidence_ids": [eid] if eid else [],
                }

            starter_rows = [player_row(player_id, started=True) for player_id in starters]
            bench_rows = [player_row(player_id, started=False) for player_id in bench]
            lineup_ready = bool(starters) and all(
                row.get("fantasy_points") is not None for row in starter_rows
            )
            if expected_slots and len(starters) != len(expected_slots):
                lineup_ready = False

            team_eid = team_evidence.get(roster_id)
            if team_eid:
                game_evidence.add(team_eid)
            ranking = (
                ranking_by_roster.get(roster_id)
                or ranking_by_team.get(team_name.casefold())
                or {}
            )
            health_rows = (
                health_by_roster.get(roster_id)
                or health_by_team.get(team_name.casefold())
                or []
            )
            for item in health_rows:
                if item.get("evidence_id"):
                    game_evidence.add(str(item["evidence_id"]))

            related_transactions = [
                dict(row)
                for row in transaction_rows
                if roster_id in [
                    int(value)
                    for value in row.get("roster_ids") or []
                    if str(value).isdigit()
                ]
                or team_name in (row.get("teams") or [])
            ]
            for transaction in related_transactions:
                game_evidence.update(
                    str(value) for value in transaction.get("evidence_ids") or []
                )

            compiled_teams.append(
                {
                    "roster_id": roster_id,
                    "team": team_name,
                    "points": float(side.get("points") or 0),
                    "entering_record": entering.get(str(roster_id)),
                    "entering_power_rank": ranking.get("previous_rank"),
                    "submitted_starters": starter_rows,
                    "bench": bench_rows,
                    "lineup_evidence_status": (
                        "READY" if lineup_ready else "UNAVAILABLE"
                    ),
                    "health_context": health_rows,
                    "transaction_context": related_transactions,
                    "evidence_ids": sorted(
                        {
                            value
                            for value in [
                                team_eid,
                                *[
                                    eid
                                    for row in starter_rows + bench_rows
                                    for eid in row.get("evidence_ids") or []
                                ],
                            ]
                            if value
                        }
                    ),
                }
            )

        if not compiled_teams and base.get("teams"):
            compiled_teams = [dict(row) for row in base.get("teams") or []]

        submitted_ready = (
            len(compiled_teams) == 2
            and all(
                row.get("lineup_evidence_status") == "READY"
                for row in compiled_teams
            )
        )
        results.append(
            {
                **dict(base),
                "teams": compiled_teams,
                "submitted_lineup_evidence_status": (
                    "READY" if submitted_ready else "UNAVAILABLE"
                ),
                "projection_evidence_status": (
                    "READY" if projections else "UNAVAILABLE"
                ),
                "projection_evidence_note": projection_error,
                "timing_context": timing.get(str(matchup_id), []),
                "evidence_ids": sorted(game_evidence),
            }
        )
    return results
