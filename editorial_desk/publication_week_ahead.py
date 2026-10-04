from __future__ import annotations

from typing import Any


def _team_directory(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    result: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        if roster_id <= 0:
            continue
        user = users.get(str(roster.get("owner_id"))) or {}
        metadata = user.get("metadata") or {}
        result[roster_id] = str(
            metadata.get("team_name")
            or user.get("display_name")
            or user.get("username")
            or f"Roster {roster_id}"
        )
    return result


def build_flagship_week_ahead(
    snapshot: dict[str, Any],
    research: dict[str, Any],
    canonical: dict[str, Any],
    health: dict[str, Any],
) -> dict[str, Any]:
    """Expand the authoritative forecast handoff for offline manuscript use."""
    source = dict(research.get("weekly_matchup_forecast") or {})
    rows = [dict(row) for row in source.get("rows") or []]
    teams = _team_directory(snapshot)
    players = snapshot.get("players") or {}
    division_records = (
        (canonical.get("division_summary") or {}).get("team_records") or {}
    )
    schedule_rows = {
        int(row.get("roster_id") or 0): dict(row)
        for row in (research.get("remaining_schedule_strength") or {}).get("rows") or []
        if row.get("roster_id") is not None
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

    season = str(
        research.get("season")
        or (snapshot.get("league") or {}).get("season")
        or ""
    )
    next_week = int(research.get("week") or snapshot.get("week") or 0) + 1

    enriched: list[dict[str, Any]] = []
    for row in rows:
        matchup_id = row.get("matchup_id")
        forecast_week = int(row.get("week") or next_week)
        roster_one = int(row.get("roster_one") or 0)
        roster_two = int(row.get("roster_two") or 0)
        evidence_id = f"ranking-forecast:{season}:{forecast_week}:{matchup_id}"

        def side(roster_id: int, suffix: str) -> dict[str, Any]:
            team_name = str(
                row.get(f"team_{suffix}")
                or teams.get(roster_id)
                or f"Roster {roster_id}"
            )
            lineup_ids = [
                str(player_id)
                for player_id in row.get(f"optimal_lineup_{suffix}") or []
                if str(player_id) != "0"
            ]
            return {
                "roster_id": roster_id,
                "team": team_name,
                "projected_score": row.get(f"projected_score_{suffix}"),
                "optimal_lineup": [
                    {
                        "player_id": player_id,
                        "player": str(
                            (players.get(player_id) or {}).get("full_name")
                            or (players.get(player_id) or {}).get("name")
                            or player_id
                        ),
                        "position": (players.get(player_id) or {}).get("position"),
                    }
                    for player_id in lineup_ids
                ],
                "health_caveats": (
                    health_by_roster.get(roster_id)
                    or health_by_team.get(team_name.casefold())
                    or []
                ),
                "division_context": division_records.get(str(roster_id)),
                "remaining_schedule_strength": schedule_rows.get(roster_id),
            }

        enriched.append(
            {
                **row,
                "week": forecast_week,
                "teams": [
                    side(roster_one, "one"),
                    side(roster_two, "two"),
                ],
                "model_source": row.get("projection_source") or row.get("model"),
                "evidence_ids": [evidence_id],
            }
        )

    source["rows"] = enriched
    return source


def build_combined_evidence_index(
    canonical: dict[str, Any],
    transactions: dict[str, Any],
    health: dict[str, Any],
    week_ahead: dict[str, Any],
) -> dict[str, Any]:
    """Index evidence references emitted outside canonical league history."""
    index = dict(canonical.get("evidence_index") or {})

    for row in transactions.get("transactions") or []:
        for evidence_id in row.get("evidence_ids") or []:
            key = str(evidence_id)
            index[key] = {
                "evidence_id": key,
                "kind": "transaction",
                "transaction_id": row.get("transaction_id"),
                "week": row.get("week"),
            }

    for row in health.get("players") or []:
        evidence_id = row.get("evidence_id")
        if evidence_id:
            key = str(evidence_id)
            index[key] = {
                "evidence_id": key,
                "kind": "health_status",
                "player_id": row.get("player_id"),
                "observed_at": row.get("observed_at"),
            }
        for event in row.get("news_events") or []:
            event_id = event.get("event_id")
            if not event_id:
                continue
            key = str(event_id)
            index[key] = {
                "evidence_id": key,
                "kind": "accepted_news",
                "player_id": row.get("player_id"),
                "published_at": event.get("published_at"),
                "source": event.get("source"),
            }

    for row in week_ahead.get("rows") or []:
        for evidence_id in row.get("evidence_ids") or []:
            key = str(evidence_id)
            index[key] = {
                "evidence_id": key,
                "kind": "weekly_matchup_forecast",
                "matchup_id": row.get("matchup_id"),
                "week": row.get("week"),
                "model_source": row.get("model_source"),
            }

    return index
