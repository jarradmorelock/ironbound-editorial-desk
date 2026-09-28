"""Deterministic Roster & Market evidence for the two flagship magazines."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


def build_market_desk(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    beat_report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble market, lineup-churn, health, and news evidence.

    This module deliberately remains useful during quiet transaction weeks.
    Transactions are one signal among lineup churn, roster construction,
    availability, and accepted beat/news context.
    """
    names = _roster_team_names(snapshot)
    players = snapshot.get("players") or {}
    transaction_ledger = _transaction_ledger(snapshot, names, players)
    starter_churn = _starter_churn(snapshot, names, players)
    roster_architecture = _roster_architecture(snapshot, names, players)
    health = dossier.get("roster_health") or {}
    health_context = [dict(row) for row in health.get("players") or []]
    beat_items = [
        dict(row)
        for row in (beat_report or {}).get("items") or []
        if any(
            (row.get("editorial_lanes") or {}).get(key)
            for key in ("health_context", "usage_context", "preview_context", "since_we_last_printed")
        )
    ]

    return {
        "status": "READY",
        "principle": (
            "Transactions are signals, not the whole story. Read moves together "
            "with starter churn, roster construction, availability, and sourced news."
        ),
        "transaction_ledger": transaction_ledger,
        "starter_churn": starter_churn,
        "roster_architecture": roster_architecture,
        "health_context": health_context,
        "beat_context": beat_items,
        "player_context_timelines": _player_context_timelines(beat_items, health_context),
        "sleeper_platform_market": {
            "status": "UNAVAILABLE",
            "scope": "platform-wide roster percentage / start percentage",
            "required": False,
            "reason": (
                "No verified stable Sleeper-wide roster/start-rate provider is "
                "configured. Do not infer or relabel league-network rates as Sleeper-wide."
            ),
        },
    }


def build_context_events(beat_report: dict[str, Any] | None) -> dict[str, Any]:
    """Index the same accepted news events for reuse across magazine departments."""
    items = [dict(row) for row in (beat_report or {}).get("items") or []]
    by_player: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in items:
        for player in event.get("league_players") or []:
            player_id = str(
                player.get("sleeper_player_id")
                or player.get("nflverse_id")
                or player.get("player")
                or ""
            )
            if player_id:
                by_player[player_id].append(event)
            team = str(player.get("fantasy_team") or "")
            if team:
                by_team[team].append(event)

    for rows in list(by_player.values()) + list(by_team.values()):
        rows.sort(key=lambda row: (str(row.get("published_at") or ""), str(row.get("event_id") or "")))

    return {
        "authority": "Ironbound-Forum-Feed-Poster",
        "events": items,
        "by_player": dict(by_player),
        "by_fantasy_team": dict(by_team),
        "reuse_policy": (
            "Use the same sourced event wherever it materially informs a game story, "
            "health, market, usage, Power Board, or preview. Do not confine news to one section."
        ),
    }


def _transaction_ledger(
    snapshot: dict[str, Any],
    names: dict[int, str],
    players: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source = (snapshot.get("flagship_sleeper") or {}).get("transactions") or {}
    weeks = source.get("weeks") or {}
    raw: dict[str, dict[str, Any]] = {}
    for week, rows in sorted(weeks.items(), key=lambda item: int(item[0])):
        for index, row in enumerate(rows or []):
            if row.get("status") != "complete":
                continue
            key = str(row.get("transaction_id") or f"week-{week}-{index}")
            raw[key] = {**row, "_week": int(week)}
    if not weeks:
        for index, row in enumerate(snapshot.get("transactions") or []):
            if row.get("status") != "complete":
                continue
            key = str(row.get("transaction_id") or f"current-{index}")
            raw[key] = dict(row)

    records: list[dict[str, Any]] = []
    for row in raw.values():
        adds = row.get("adds") or {}
        drops = row.get("drops") or {}
        moves = []
        for player_id in sorted(set(adds) | set(drops)):
            from_id = _int_or_none(drops.get(player_id))
            to_id = _int_or_none(adds.get(player_id))
            moves.append(
                {
                    "player_id": str(player_id),
                    "player": _player_name(str(player_id), players),
                    "from_roster_id": from_id,
                    "from_team": names.get(from_id, "Free agency") if from_id else "Free agency",
                    "to_roster_id": to_id,
                    "to_team": names.get(to_id, "Free agency") if to_id else "Free agency",
                }
            )
        created = int(row.get("created") or 0)
        records.append(
            {
                "transaction_id": row.get("transaction_id"),
                "week": row.get("_week"),
                "type": row.get("type"),
                "created": created,
                "occurred_at": (
                    datetime.fromtimestamp(created / 1000, timezone.utc).isoformat()
                    if created else None
                ),
                "teams": [
                    names.get(int(roster_id), f"Roster {roster_id}")
                    for roster_id in row.get("roster_ids") or []
                ],
                "player_moves": moves,
                "faab_bid": (row.get("settings") or {}).get("waiver_bid"),
                "draft_picks": [dict(pick) for pick in row.get("draft_picks") or []],
            }
        )
    records.sort(key=lambda row: (int(row.get("created") or 0), str(row.get("transaction_id") or "")), reverse=True)
    return {
        "status": source.get("status", "current_week_only"),
        "season_summary": {
            "completed": len(records),
            "trades": sum(row.get("type") == "trade" for row in records),
            "waivers": sum(row.get("type") == "waiver" for row in records),
            "free_agents": sum(row.get("type") == "free_agent" for row in records),
        },
        "records": records,
    }


def _starter_churn(
    snapshot: dict[str, Any],
    names: dict[int, str],
    players: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    schedule = ((snapshot.get("flagship_sleeper") or {}).get("schedule") or {}).get("weeks") or {}
    current_week = int(snapshot.get("week") or 0)
    previous_week = current_week - 1
    current = _starter_map(schedule.get(str(current_week)) or schedule.get(current_week) or [])
    previous = _starter_map(schedule.get(str(previous_week)) or schedule.get(previous_week) or [])
    rows = []
    for roster_id in sorted(set(current) | set(previous)):
        promoted = sorted(current.get(roster_id, set()) - previous.get(roster_id, set()))
        demoted = sorted(previous.get(roster_id, set()) - current.get(roster_id, set()))
        if not promoted and not demoted:
            continue
        rows.append(
            {
                "roster_id": roster_id,
                "team": names.get(roster_id, f"Roster {roster_id}"),
                "from_week": previous_week,
                "to_week": current_week,
                "promoted": [
                    {"player_id": player_id, "player": _player_name(player_id, players)}
                    for player_id in promoted
                ],
                "demoted": [
                    {"player_id": player_id, "player": _player_name(player_id, players)}
                    for player_id in demoted
                ],
            }
        )
    return rows


def _starter_map(rows: list[dict[str, Any]]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for row in rows:
        roster_id = _int_or_none(row.get("roster_id"))
        if roster_id is None:
            continue
        result[roster_id] = {str(value) for value in row.get("starters") or [] if value}
    return result


def _roster_architecture(
    snapshot: dict[str, Any],
    names: dict[int, str],
    players: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        ids = [str(value) for value in roster.get("players") or []]
        positions = Counter(
            str((players.get(player_id) or {}).get("position") or "UNK")
            for player_id in ids
        )
        total = max(1, len(ids))
        rows.append(
            {
                "roster_id": roster_id,
                "team": names.get(roster_id, f"Roster {roster_id}"),
                "listed_players": len(ids),
                "position_counts": dict(sorted(positions.items())),
                "position_shares": {
                    position: round(count / total, 4)
                    for position, count in sorted(positions.items())
                },
            }
        )
    return sorted(rows, key=lambda row: int(row["roster_id"]))


def _player_context_timelines(
    beat_items: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_player: dict[str, dict[str, Any]] = {}
    for event in beat_items:
        for mapped in event.get("league_players") or []:
            key = str(mapped.get("sleeper_player_id") or mapped.get("player") or "")
            if not key:
                continue
            target = by_player.setdefault(
                key,
                {
                    "player_id": mapped.get("sleeper_player_id"),
                    "player": mapped.get("player"),
                    "team": mapped.get("fantasy_team"),
                    "events": [],
                    "current_health": None,
                },
            )
            target["events"].append(
                {
                    "published_at": event.get("published_at"),
                    "headline": event.get("headline") or event.get("original_title"),
                    "source": event.get("source"),
                    "source_url": event.get("source_url"),
                    "tags": list(event.get("tags") or []),
                }
            )
    for row in health_rows:
        key = str(row.get("player_id") or row.get("sleeper_player_id") or row.get("player") or "")
        if not key:
            continue
        target = by_player.setdefault(
            key,
            {
                "player_id": row.get("player_id") or row.get("sleeper_player_id"),
                "player": row.get("player"),
                "team": row.get("team"),
                "events": [],
                "current_health": None,
            },
        )
        target["current_health"] = dict(row)
    result = list(by_player.values())
    for row in result:
        row["events"].sort(key=lambda value: str(value.get("published_at") or ""))
    return sorted(result, key=lambda row: (str(row.get("team") or ""), str(row.get("player") or "")))


def _roster_team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    result = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        result[roster_id] = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
    return result


def _player_name(player_id: str, players: dict[str, dict[str, Any]]) -> str:
    row = players.get(str(player_id)) or {}
    return str(row.get("full_name") or row.get("name") or player_id)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
