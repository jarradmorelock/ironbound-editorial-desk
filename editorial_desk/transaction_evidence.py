from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


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


def _publication_context(snapshot: dict[str, Any]) -> dict[str, Any]:
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
        roster_id = _safe_int(roster.get("roster_id"))
        if roster_id is None:
            continue
        owner = users.get(str(roster.get("owner_id") or "")) or {}
        metadata = owner.get("metadata") or {}
        names[roster_id] = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
    return names


def _player_name(players: dict[str, Any], player_id: str) -> str:
    row = players.get(str(player_id)) or {}
    return str(row.get("full_name") or row.get("name") or player_id)


def _completed_at(value: Any) -> str | None:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return None
    # Sleeper transaction created timestamps are milliseconds.
    if raw > 10_000_000_000:
        raw /= 1000.0
    try:
        return datetime.fromtimestamp(raw, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _transaction_richness(row: dict[str, Any]) -> int:
    return (
        len(row.get("adds") or {})
        + len(row.get("drops") or {})
        + 2 * len(row.get("draft_picks") or [])
        + len(row.get("roster_ids") or [])
    )


def _chronicle_event_ids(
    chronicle: Any | None,
    *,
    league_key: str,
    transaction_id: str,
) -> list[str]:
    if chronicle is None or not hasattr(chronicle, "league_events"):
        return []
    try:
        events = chronicle.league_events(league_key)
    except (OSError, ValueError, KeyError, TypeError):
        return []
    matches: list[str] = []
    for event in events or []:
        evidence = event.get("evidence") or {}
        entities = event.get("entities") or {}
        candidate = (
            evidence.get("transaction_id")
            or entities.get("transaction_id")
        )
        if str(candidate or "") != transaction_id:
            continue
        event_id = event.get("event_id")
        if event_id:
            matches.append(str(event_id))
    return sorted(set(matches))


def _normalize_transaction(
    snapshot: dict[str, Any],
    row: dict[str, Any],
    *,
    week: int,
    source_weeks: list[int],
    chronicle: Any | None,
) -> dict[str, Any]:
    players = snapshot.get("players") or {}
    teams = _team_names(snapshot)
    league_key = str((snapshot.get("editorial") or {}).get("league_key") or "")
    transaction_id = str(row.get("transaction_id") or "")
    settings = row.get("settings") or {}

    add_map = {
        str(player_id): _safe_int(roster_id)
        for player_id, roster_id in (row.get("adds") or {}).items()
    }
    drop_map = {
        str(player_id): _safe_int(roster_id)
        for player_id, roster_id in (row.get("drops") or {}).items()
    }

    adds = [
        {
            "player_id": player_id,
            "player": _player_name(players, player_id),
            "to_roster_id": roster_id,
            "to_team": teams.get(roster_id) if roster_id is not None else None,
        }
        for player_id, roster_id in add_map.items()
    ]
    drops = [
        {
            "player_id": player_id,
            "player": _player_name(players, player_id),
            "from_roster_id": roster_id,
            "from_team": teams.get(roster_id) if roster_id is not None else None,
        }
        for player_id, roster_id in drop_map.items()
    ]

    received_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sent_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_player_ids = sorted(set(add_map) | set(drop_map))
    player_rows: list[dict[str, Any]] = []
    for player_id in all_player_ids:
        to_roster_id = add_map.get(player_id)
        from_roster_id = drop_map.get(player_id)
        value = {
            "player_id": player_id,
            "player": _player_name(players, player_id),
            "from_roster_id": from_roster_id,
            "from_team": teams.get(from_roster_id)
            if from_roster_id is not None
            else None,
            "to_roster_id": to_roster_id,
            "to_team": teams.get(to_roster_id)
            if to_roster_id is not None
            else None,
        }
        player_rows.append(value)
        if to_roster_id is not None:
            received_by[
                teams.get(to_roster_id, f"Roster {to_roster_id}")
            ].append(dict(value))
        if from_roster_id is not None:
            sent_by[
                teams.get(from_roster_id, f"Roster {from_roster_id}")
            ].append(dict(value))

    warnings: list[str] = []
    picks: list[dict[str, Any]] = []
    for raw_pick in row.get("draft_picks") or []:
        original = _safe_int(raw_pick.get("roster_id"))
        previous = _safe_int(raw_pick.get("previous_owner_id"))
        new_owner = _safe_int(raw_pick.get("owner_id"))
        pick = {
            "season": str(raw_pick.get("season") or ""),
            "round": _safe_int(raw_pick.get("round")),
            "original_roster_id": original,
            "original_team": teams.get(original) if original is not None else None,
            "previous_owner_roster_id": previous,
            "previous_owner_team": teams.get(previous)
            if previous is not None
            else None,
            "new_owner_roster_id": new_owner,
            "new_owner_team": teams.get(new_owner)
            if new_owner is not None
            else None,
            "league_id": raw_pick.get("league_id"),
        }
        unresolved = [
            label
            for label, roster_id, team in (
                ("original", original, pick["original_team"]),
                ("previous owner", previous, pick["previous_owner_team"]),
                ("new owner", new_owner, pick["new_owner_team"]),
            )
            if roster_id is not None and team is None
        ]
        if unresolved:
            warnings.append(
                f"Draft pick {pick['season']} round {pick['round']} has unresolved "
                + ", ".join(unresolved)
                + " roster identity."
            )
        picks.append(pick)

    roster_ids = [
        rid
        for rid in (
            _safe_int(value) for value in (row.get("roster_ids") or [])
        )
        if rid is not None
    ]
    participant_rows = [
        {
            "roster_id": roster_id,
            "team": teams.get(roster_id, f"Roster {roster_id}"),
        }
        for roster_id in roster_ids
    ]

    faab = _safe_float(
        settings.get("waiver_bid")
        if settings.get("waiver_bid") is not None
        else settings.get("amount")
    )
    chronicle_ids = _chronicle_event_ids(
        chronicle,
        league_key=league_key,
        transaction_id=transaction_id,
    )
    evidence_ids = [f"sleeper-transaction:{transaction_id}"]
    evidence_ids.extend(chronicle_ids)

    return {
        "transaction_id": transaction_id,
        "week": int(week),
        "source_weeks": sorted(set(int(value) for value in source_weeks)),
        "type": row.get("type"),
        "status": row.get("status"),
        "created": row.get("created"),
        "completed_at": _completed_at(row.get("created")),
        "roster_ids": roster_ids,
        "teams": participant_rows,
        # Compatibility fields retained for existing market consumers.
        "adds": adds,
        "drops": drops,
        "players": {
            "all": player_rows,
            "received_by": {
                key: sorted(value, key=lambda item: str(item["player"]).casefold())
                for key, value in sorted(received_by.items())
            },
            "sent_by": {
                key: sorted(value, key=lambda item: str(item["player"]).casefold())
                for key, value in sorted(sent_by.items())
            },
        },
        "draft_picks": picks,
        "faab": faab,
        "warnings": warnings,
        "evidence_ids": evidence_ids,
    }


def build_transaction_evidence(
    snapshot: dict[str, Any],
    chronicle: Any | None = None,
) -> dict[str, Any]:
    """Normalize completed Sleeper transactions through the reviewed week.

    Sleeper transaction payloads remain authoritative for exact player, pick,
    FAAB, and roster movement terms. Chronicle event IDs are attached only as
    additional provenance.
    """

    through_week = int(snapshot.get("week") or 0)
    context = _publication_context(snapshot)
    transaction_source = context.get("transactions") or {}
    weeks = transaction_source.get("weeks") or {}

    candidates: dict[str, dict[str, Any]] = {}
    source_weeks: dict[str, set[int]] = defaultdict(set)

    if isinstance(weeks, dict) and weeks:
        for raw_week, values in weeks.items():
            try:
                week = int(raw_week)
            except (TypeError, ValueError):
                continue
            if not (0 < week <= through_week):
                continue
            for row in values or []:
                if not isinstance(row, dict) or row.get("status") != "complete":
                    continue
                transaction_id = str(
                    row.get("transaction_id")
                    or f"anonymous:{week}:{len(candidates)}"
                )
                source_weeks[transaction_id].add(week)
                previous = candidates.get(transaction_id)
                if previous is None or _transaction_richness(row) > _transaction_richness(
                    previous["row"]
                ):
                    candidates[transaction_id] = {"week": week, "row": dict(row)}
    else:
        for row in snapshot.get("transactions") or []:
            if not isinstance(row, dict) or row.get("status") != "complete":
                continue
            transaction_id = str(
                row.get("transaction_id")
                or f"anonymous:{through_week}:{len(candidates)}"
            )
            source_weeks[transaction_id].add(through_week)
            candidates[transaction_id] = {
                "week": through_week,
                "row": dict(row),
            }

    normalized = [
        _normalize_transaction(
            snapshot,
            value["row"],
            week=int(value["week"]),
            source_weeks=sorted(source_weeks[transaction_id]),
            chronicle=chronicle,
        )
        for transaction_id, value in candidates.items()
    ]
    normalized.sort(
        key=lambda row: (
            int(row.get("week") or 0),
            str(row.get("completed_at") or ""),
            str(row.get("transaction_id") or ""),
        )
    )

    warnings = [
        {
            "transaction_id": row["transaction_id"],
            "warning": warning,
        }
        for row in normalized
        for warning in row.get("warnings") or []
    ]
    pick_status = "READY" if not warnings else "PARTIAL"

    source_status = str(transaction_source.get("status") or "")
    if not source_status:
        source_status = "available" if snapshot.get("transactions") is not None else "unavailable"
    source_errors = transaction_source.get("errors") or {}

    return {
        "schema_version": 1,
        "through_week": through_week,
        "coverage": {
            "status": (
                "READY"
                if source_status == "available"
                else "PARTIAL"
                if source_status == "partial"
                else "UNAVAILABLE"
            ),
            "source_status": source_status,
            "weeks": sorted(
                {
                    week
                    for values in source_weeks.values()
                    for week in values
                }
            ),
            "errors": dict(source_errors),
        },
        "pick_provenance_status": pick_status,
        "warnings": warnings,
        "transactions": normalized,
    }
