from __future__ import annotations

from typing import Any


def build_roster_health(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build the publication health block from Sleeper roster/player metadata.

    Every publication receives basic player status, injury designation, and
    reserve/IR placement. Flagship publications additionally retain the richer
    practice and injury context already collected for Ironbound and Unbound.
    """
    rosters = snapshot.get("rosters") or []
    raw_players = snapshot.get("players")
    if not isinstance(raw_players, dict):
        return {
            "status": "unavailable",
            "players": [],
            "error": "Sleeper player metadata was not collected",
        }

    rostered_ids = {
        str(player_id)
        for roster in rosters
        for player_id in (roster.get("players") or [])
    }
    if rostered_ids and not raw_players:
        return {
            "status": "unavailable",
            "players": [],
            "error": "Sleeper player metadata was empty for rostered players",
        }

    editorial = snapshot.get("editorial") or {}
    expanded = str(editorial.get("tier") or "").casefold() == "flagship"
    users = {
        str(user.get("user_id")): user for user in snapshot.get("users") or []
    }
    alerts: list[dict[str, Any]] = []

    for roster in rosters:
        roster_id = int(roster.get("roster_id") or 0)
        owner = users.get(str(roster.get("owner_id"))) or {}
        owner_metadata = owner.get("metadata") or {}
        team = str(
            owner_metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
        reserve = {str(player_id) for player_id in roster.get("reserve") or []}

        for raw_player_id in roster.get("players") or []:
            player_id = str(raw_player_id)
            player = raw_players.get(player_id) or {}
            status = str(player.get("status") or "").strip()
            injury_status = player.get("injury_status")
            on_ir = player_id in reserve
            practice = player.get("practice_participation") if expanded else None

            generally_flagged = bool(
                on_ir
                or injury_status
                or status.casefold() not in {"", "active"}
            )
            if not generally_flagged and not (expanded and practice):
                continue

            row: dict[str, Any] = {
                "roster_id": roster_id,
                "team": team,
                "manager": owner.get("display_name"),
                "player_id": player_id,
                "player": str(player.get("full_name") or player_id),
                "position": player.get("position"),
                "nfl_team": player.get("team"),
                "status": status or None,
                "injury_status": injury_status,
                "on_ir": on_ir,
            }
            if expanded:
                row.update(
                    {
                        "practice_participation": practice,
                        "injury_start_date": player.get("injury_start_date"),
                        "depth_chart_order": player.get("depth_chart_order"),
                        "news_updated": player.get("news_updated"),
                    }
                )
            alerts.append(row)

    alerts.sort(
        key=lambda row: (
            str(row.get("team") or "").casefold(),
            str(row.get("player") or "").casefold(),
        )
    )
    return {"status": "available", "players": alerts}


def render_roster_health(health: dict[str, Any], *, expanded: bool) -> list[str]:
    lines = ["## Roster Health", ""]
    status = str(health.get("status") or "not_collected")
    if status != "available":
        error = str(health.get("error") or "upstream Sleeper health data unavailable")
        lines.append(f"- Roster health data unavailable: {error}")
        return lines

    players = health.get("players") or []
    if not players:
        lines.append("- No roster health flags returned")
        return lines

    for row in players:
        details: list[str] = []
        if row.get("status"):
            details.append(str(row["status"]))
        if row.get("injury_status"):
            details.append(str(row["injury_status"]))
        if row.get("on_ir"):
            details.append("IR/RESERVE")
        if expanded:
            if row.get("practice_participation"):
                details.append(str(row["practice_participation"]))
            if row.get("injury_start_date"):
                details.append(f"injury start {row['injury_start_date']}")
            if row.get("depth_chart_order") is not None:
                details.append(f"depth chart {row['depth_chart_order']}")

        position = row.get("position") or "N/A"
        nfl_team = row.get("nfl_team") or "FA"
        detail_text = ", ".join(details) if details else "flagged"
        lines.append(
            f"- {row.get('team')}: {row.get('player')} "
            f"({position}, {nfl_team}) — {detail_text}"
        )
    return lines
