"""Deterministic roster, health, transaction, and market research for flagships."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def build_network_market_context(
    snapshots: list[dict[str, Any]],
    week: int,
) -> dict[str, Any]:
    """Aggregate cross-league add signals without pretending they are Sleeper-wide."""
    adds: dict[str, dict[str, Any]] = {}
    leagues_by_player: dict[str, set[str]] = defaultdict(set)
    tx_count: Counter[str] = Counter()
    names: dict[str, str] = {}

    for snapshot in snapshots:
        if int(snapshot.get("week") or 0) != int(week):
            continue
        league_key = str((snapshot.get("editorial") or {}).get("league_key") or "")
        players = snapshot.get("players") or {}
        for transaction in snapshot.get("transactions") or []:
            for player_id in (transaction.get("adds") or {}):
                player_id = str(player_id)
                tx_count[player_id] += 1
                if league_key:
                    leagues_by_player[player_id].add(league_key)
                names[player_id] = str(
                    (players.get(player_id) or {}).get("full_name")
                    or (players.get(player_id) or {}).get("name")
                    or player_id
                )

    for player_id, count in tx_count.items():
        adds[player_id] = {
            "player_id": player_id,
            "player": names.get(player_id, player_id),
            "league_count": len(leagues_by_player[player_id]),
            "transaction_count": int(count),
            "league_keys": sorted(leagues_by_player[player_id]),
            "scope": "tracked_leagues",
        }
    return {
        "week": int(week),
        "player_adds": adds,
        "scope": "all collected Sleeper leagues in this Editorial Desk run",
    }


def build_roster_market(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    *,
    beat_report: dict[str, Any] | None = None,
    network_market: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a quiet-week-safe Roster & Market research layer.

    A week with no blockbuster trade should still surface starter churn, roster
    construction, repeated asset movement, current health, and relevant beat
    context. This layer does not invent platform-wide rates.
    """
    flagship = snapshot.get("flagship_sleeper") or {}
    schedule = flagship.get("schedule") or {}
    transactions_source = flagship.get("transactions") or {}
    schedule_ready = schedule.get("status") in {"available", "partial"}
    transaction_ready = transactions_source.get("status") in {"available", "partial"}
    week = int(snapshot.get("week") or dossier.get("week") or 0)
    player_names = {
        str(player_id): str(
            player.get("full_name") or player.get("name") or player_id
        )
        for player_id, player in (snapshot.get("players") or {}).items()
    }
    team_names = _roster_team_names(snapshot)
    beat_by_player = _beat_events_by_player(beat_report)

    churn = _starter_churn(
        schedule,
        week,
        player_names=player_names,
        team_names=team_names,
        beat_by_player=beat_by_player,
    )
    current_transactions = _normalize_current_transactions(
        snapshot.get("transactions") or [],
        player_names=player_names,
        team_names=team_names,
        beat_by_player=beat_by_player,
    )
    history = _transaction_history(
        transactions_source,
        week,
        player_names=player_names,
    )
    architecture = _roster_architecture(snapshot, team_names)
    health = _health_timelines(
        dossier.get("roster_health") or {},
        beat_by_player=beat_by_player,
    )
    network_signals = sorted(
        [
            dict(row)
            for row in ((network_market or {}).get("player_adds") or {}).values()
            if int(row.get("league_count") or 0) > 1
        ],
        key=lambda row: (
            -int(row.get("league_count") or 0),
            -int(row.get("transaction_count") or 0),
            str(row.get("player") or "").casefold(),
        ),
    )

    return {
        "status": "READY" if schedule_ready and transaction_ready else "MANUAL_VERIFY",
        "source_status": {
            "full_schedule": schedule.get("status") or "missing",
            "transaction_history": transactions_source.get("status") or "missing",
            "roster_health": (dossier.get("roster_health") or {}).get("status")
            or "missing",
            "beat_news": (beat_report or {}).get("status") if beat_report else "not_configured",
        },
        "starter_churn": churn,
        "current_transactions": current_transactions,
        "transaction_history": history,
        "roster_architecture": architecture,
        "health_timelines": health,
        "network_add_signals": network_signals[:15],
        "platform_market_rates": {
            "status": "UNAVAILABLE",
            "required": False,
            "scope": "Sleeper-wide roster/start percentage",
            "note": (
                "No verified durable provider is integrated. Do not label tracked-league "
                "rates as Sleeper-wide. This optional field may become EXPERIMENTAL or "
                "READY when a verified source is added."
            ),
        },
        "editorial_policy": (
            "Health, transactions, starter changes, roster shape, market movement, "
            "and beat-report timelines share one research layer. News evidence may "
            "also be reused in game recaps, Usage Desk, and previews."
        ),
    }


def _starter_churn(
    schedule: dict[str, Any],
    week: int,
    *,
    player_names: dict[str, str],
    team_names: dict[int, str],
    beat_by_player: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    weeks = schedule.get("weeks") or {}
    previous_rows = {
        int(row.get("roster_id") or 0): row
        for row in weeks.get(str(max(1, week - 1))) or []
        if row.get("roster_id") is not None
    }
    current_rows = {
        int(row.get("roster_id") or 0): row
        for row in weeks.get(str(week)) or []
        if row.get("roster_id") is not None
    }
    rows: list[dict[str, Any]] = []
    for roster_id in sorted(set(previous_rows) | set(current_rows)):
        previous = {str(v) for v in (previous_rows.get(roster_id) or {}).get("starters") or []}
        current = {str(v) for v in (current_rows.get(roster_id) or {}).get("starters") or []}
        moved_out = [
            _player_change(player_id, player_names, beat_by_player)
            for player_id in sorted(previous - current)
        ]
        moved_in = [
            _player_change(player_id, player_names, beat_by_player)
            for player_id in sorted(current - previous)
        ]
        if moved_out or moved_in:
            rows.append(
                {
                    "roster_id": roster_id,
                    "team": team_names.get(roster_id, f"Roster {roster_id}"),
                    "from_week": max(1, week - 1),
                    "to_week": week,
                    "moved_out": moved_out,
                    "moved_in": moved_in,
                }
            )
    return rows


def _player_change(
    player_id: str,
    player_names: dict[str, str],
    beat_by_player: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "player": player_names.get(player_id, player_id),
        "context_events": [dict(row) for row in beat_by_player.get(player_id, [])],
    }


def _normalize_current_transactions(
    transactions: list[dict[str, Any]],
    *,
    player_names: dict[str, str],
    team_names: dict[int, str],
    beat_by_player: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tx in transactions:
        settings = tx.get("settings") or {}
        adds = [
            {
                "player_id": str(player_id),
                "player": player_names.get(str(player_id), str(player_id)),
                "roster_id": _int_or_none(roster_id),
                "team": team_names.get(_int_or_none(roster_id) or 0),
                "context_events": [
                    dict(row) for row in beat_by_player.get(str(player_id), [])
                ],
            }
            for player_id, roster_id in (tx.get("adds") or {}).items()
        ]
        drops = [
            {
                "player_id": str(player_id),
                "player": player_names.get(str(player_id), str(player_id)),
                "roster_id": _int_or_none(roster_id),
                "team": team_names.get(_int_or_none(roster_id) or 0),
                "context_events": [
                    dict(row) for row in beat_by_player.get(str(player_id), [])
                ],
            }
            for player_id, roster_id in (tx.get("drops") or {}).items()
        ]
        rows.append(
            {
                "transaction_id": tx.get("transaction_id"),
                "type": tx.get("type"),
                "status": tx.get("status"),
                "adds": adds,
                "drops": drops,
                "faab": _numeric(
                    settings.get("waiver_bid")
                    if settings.get("waiver_bid") is not None
                    else settings.get("faab")
                ),
                "raw_roster_ids": list(tx.get("roster_ids") or []),
            }
        )
    return rows


def _transaction_history(
    source: dict[str, Any],
    week: int,
    *,
    player_names: dict[str, str],
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    types: dict[str, Counter[str]] = defaultdict(Counter)
    weeks_seen: dict[str, set[int]] = defaultdict(set)
    for raw_week, rows in (source.get("weeks") or {}).items():
        try:
            tx_week = int(raw_week)
        except (TypeError, ValueError):
            continue
        if tx_week > week:
            continue
        for tx in rows or []:
            player_ids = set(str(v) for v in (tx.get("adds") or {}))
            player_ids.update(str(v) for v in (tx.get("drops") or {}))
            for player_id in player_ids:
                counts[player_id] += 1
                types[player_id][str(tx.get("type") or "unknown")] += 1
                weeks_seen[player_id].add(tx_week)
    rows = [
        {
            "player_id": player_id,
            "player": player_names.get(player_id, player_id),
            "event_count": int(count),
            "weeks": sorted(weeks_seen[player_id]),
            "transaction_types": dict(types[player_id]),
        }
        for player_id, count in counts.items()
    ]
    rows.sort(
        key=lambda row: (
            -int(row["event_count"]),
            str(row["player"]).casefold(),
        )
    )
    return rows[:25]


def _roster_architecture(
    snapshot: dict[str, Any],
    team_names: dict[int, str],
) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    rows: list[dict[str, Any]] = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        ids = [str(v) for v in roster.get("players") or []]
        counts = Counter(
            str((players.get(player_id) or {}).get("position") or "OTHER")
            for player_id in ids
        )
        total = max(1, len(ids))
        largest_position, largest_count = (
            max(counts.items(), key=lambda item: (item[1], item[0]))
            if counts
            else ("OTHER", 0)
        )
        rows.append(
            {
                "roster_id": roster_id,
                "team": team_names.get(roster_id, f"Roster {roster_id}"),
                "total_players": len(ids),
                "position_counts": dict(sorted(counts.items())),
                "largest_position_group": largest_position,
                "largest_position_count": largest_count,
                "largest_position_share": round(largest_count / total, 3),
            }
        )
    return rows


def _health_timelines(
    health: dict[str, Any],
    *,
    beat_by_player: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for player in health.get("players") or []:
        player_id = str(player.get("player_id") or "")
        rows.append(
            {
                "player_id": player_id or None,
                "player": player.get("player"),
                "team": player.get("team"),
                "current_status": {
                    "injury_status": player.get("injury_status"),
                    "practice_participation": player.get("practice_participation"),
                    "report_primary_injury": player.get("report_primary_injury"),
                    "on_ir": bool(player.get("on_ir")),
                },
                "news_timeline": [
                    dict(row) for row in beat_by_player.get(player_id, [])
                ]
                if player_id
                else [],
            }
        )
    return rows


def _beat_events_by_player(
    beat_report: dict[str, Any] | None,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in (beat_report or {}).get("items") or []:
        for player in item.get("league_players") or []:
            player_id = str(player.get("sleeper_player_id") or "")
            if not player_id:
                continue
            result[player_id].append(
                {
                    "event_id": item.get("event_id"),
                    "published_at": item.get("published_at"),
                    "headline": item.get("headline") or item.get("original_title"),
                    "source": item.get("source"),
                    "source_url": item.get("source_url"),
                    "tags": list(item.get("tags") or []),
                    "feed_summary": item.get("feed_summary"),
                    "editorial_lanes": dict(item.get("editorial_lanes") or {}),
                }
            )
    for rows in result.values():
        rows.sort(key=lambda row: str(row.get("published_at") or ""))
    return result


def _roster_team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {
        str(row.get("user_id")): row for row in snapshot.get("users") or []
    }
    names: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        names[roster_id] = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
    return names


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _numeric(value: Any) -> float | int | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number
