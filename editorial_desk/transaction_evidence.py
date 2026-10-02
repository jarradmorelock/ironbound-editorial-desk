from __future__ import annotations

from collections import defaultdict
from typing import Any

from .chronicle_queries import ChronicleQueries


def _history(snapshot: dict[str, Any]) -> dict[str, Any]:
    return snapshot.get("publication_sleeper") or snapshot.get("flagship_sleeper") or {}


def _team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    names: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        user = users.get(str(roster.get("owner_id"))) or {}
        metadata = user.get("metadata") or {}
        names[roster_id] = str(
            metadata.get("team_name")
            or user.get("display_name")
            or f"Roster {roster_id}"
        )
    return names


def _player_name(snapshot: dict[str, Any], player_id: str) -> str:
    return str(
        ((snapshot.get("players") or {}).get(str(player_id)) or {}).get("full_name")
        or player_id
    )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _completed_transactions(snapshot: dict[str, Any]) -> tuple[list[tuple[int, dict[str, Any]]], str]:
    current_week = int(snapshot.get("week") or 0)
    history = _history(snapshot)
    source = (history.get("transactions") or {})
    weeks = source.get("weeks") or {}
    status = str(source.get("status") or "").lower()

    rows: list[tuple[int, dict[str, Any]]] = []
    if isinstance(weeks, dict) and weeks:
        for week_key, values in weeks.items():
            try:
                week = int(week_key)
            except (TypeError, ValueError):
                continue
            if week > current_week:
                continue
            for row in values or []:
                if isinstance(row, dict) and row.get("status") == "complete":
                    rows.append((week, dict(row)))
    else:
        for row in snapshot.get("transactions") or []:
            if isinstance(row, dict) and row.get("status") == "complete":
                rows.append((current_week, dict(row)))
        if rows and not status:
            status = "available"

    seen: set[str] = set()
    unique: list[tuple[int, dict[str, Any]]] = []
    for week, row in sorted(rows, key=lambda item: (item[0], int(item[1].get("created") or 0))):
        key = str(row.get("transaction_id") or f"{week}:{repr(sorted(row.items()))}")
        if key in seen:
            continue
        seen.add(key)
        unique.append((week, row))
    return unique, status or ("available" if unique else "unknown")


def _normalize_players(
    snapshot: dict[str, Any],
    row: dict[str, Any],
    team_names: dict[int, str],
) -> dict[str, Any]:
    received_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sent_by: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for player_id, roster_id_raw in (row.get("adds") or {}).items():
        roster_id = _safe_int(roster_id_raw)
        team = team_names.get(roster_id or 0, f"Roster {roster_id}")
        received_by[team].append(
            {
                "player_id": str(player_id),
                "player": _player_name(snapshot, str(player_id)),
                "roster_id": roster_id,
            }
        )

    for player_id, roster_id_raw in (row.get("drops") or {}).items():
        roster_id = _safe_int(roster_id_raw)
        team = team_names.get(roster_id or 0, f"Roster {roster_id}")
        sent_by[team].append(
            {
                "player_id": str(player_id),
                "player": _player_name(snapshot, str(player_id)),
                "roster_id": roster_id,
            }
        )

    return {
        "received_by": {key: value for key, value in sorted(received_by.items())},
        "sent_by": {key: value for key, value in sorted(sent_by.items())},
    }


def _normalize_pick(pick: dict[str, Any], team_names: dict[int, str]) -> dict[str, Any]:
    original = _safe_int(pick.get("roster_id"))
    previous = _safe_int(pick.get("previous_owner_id"))
    new_owner = _safe_int(
        pick.get("owner_id")
        if pick.get("owner_id") is not None
        else pick.get("new_owner_id")
    )
    return {
        "season": str(pick.get("season") or ""),
        "round": _safe_int(pick.get("round")),
        "original_roster_id": original,
        "original_team": team_names.get(original or 0),
        "previous_owner_roster_id": previous,
        "previous_owner_team": team_names.get(previous or 0),
        "new_owner_roster_id": new_owner,
        "new_owner_team": team_names.get(new_owner or 0),
        "raw": dict(pick),
    }


def build_transaction_evidence(
    snapshot: dict[str, Any],
    chronicle: ChronicleQueries | None = None,
) -> dict[str, Any]:
    """Normalize completed Sleeper transactions into writer-ready evidence.

    Sleeper is authoritative for exact transaction compensation. Chronicle is
    retained as corroborating provenance by downstream consumers; this builder
    does not replace exact Sleeper terms with inferred history.
    """
    team_names = _team_names(snapshot)
    transactions, source_status = _completed_transactions(snapshot)

    normalized: list[dict[str, Any]] = []
    unresolved_picks: list[dict[str, Any]] = []
    for week, row in transactions:
        settings = row.get("settings") or {}
        picks = [
            _normalize_pick(dict(pick), team_names)
            for pick in (row.get("draft_picks") or [])
            if isinstance(pick, dict)
        ]
        for pick in picks:
            if (
                pick["original_roster_id"] is None
                or pick["previous_owner_roster_id"] is None
                or pick["new_owner_roster_id"] is None
            ):
                unresolved_picks.append(
                    {
                        "transaction_id": row.get("transaction_id"),
                        "week": week,
                        "pick": pick,
                    }
                )

        roster_ids = [
            value
            for value in (_safe_int(v) for v in row.get("roster_ids") or [])
            if value is not None
        ]
        transaction_id = str(row.get("transaction_id") or "")
        normalized.append(
            {
                "transaction_id": transaction_id,
                "week": week,
                "type": row.get("type"),
                "status": row.get("status"),
                "completed_at": row.get("created"),
                "roster_ids": roster_ids,
                "teams": [team_names.get(rid, f"Roster {rid}") for rid in roster_ids],
                "players": _normalize_players(snapshot, row, team_names),
                "draft_picks": picks,
                "faab": _safe_float(
                    settings.get("waiver_bid")
                    if settings.get("waiver_bid") is not None
                    else settings.get("amount")
                ),
                "evidence_ids": [f"sleeper-transaction:{transaction_id}"]
                if transaction_id
                else [],
            }
        )

    if source_status in {"unavailable", "partial"}:
        coverage_status = source_status.upper()
    else:
        coverage_status = "READY"

    return {
        "schema_version": 1,
        "through_week": int(snapshot.get("week") or 0),
        "coverage": {
            "status": coverage_status,
            "source_status": source_status,
            "transaction_count": len(normalized),
        },
        "pick_provenance_status": "PARTIAL" if unresolved_picks else "READY",
        "unresolved_pick_provenance": unresolved_picks,
        "transactions": normalized,
    }
