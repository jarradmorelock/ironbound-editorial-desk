from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .market_rates import timestamp
from .beat_news import _reporting_window
from .chronicle_queries import ChronicleQueries
from .transaction_evidence import build_transaction_evidence


def build_network_market_context(
    snapshots: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build explicitly scoped cross-league roster/start/transaction signals.

    These rates describe only the leagues collected by Editorial Desk. They are
    never labeled Sleeper-wide.
    """
    rostered_leagues: dict[str, set[str]] = defaultdict(set)
    started_leagues: dict[str, set[str]] = defaultdict(set)
    add_leagues: dict[str, set[str]] = defaultdict(set)
    drop_leagues: dict[str, set[str]] = defaultdict(set)
    names: dict[str, str] = {}

    for league_key, snapshot in snapshots.items():
        players = snapshot.get("players") or {}
        for player_id, player in players.items():
            names[str(player_id)] = str(
                (player or {}).get("full_name") or player_id
            )
        for roster in snapshot.get("rosters") or []:
            for player_id in roster.get("players") or []:
                rostered_leagues[str(player_id)].add(str(league_key))
        for matchup in snapshot.get("matchups") or []:
            for player_id in matchup.get("starters") or []:
                if player_id and str(player_id) != "0":
                    started_leagues[str(player_id)].add(str(league_key))
        for tx in _current_transactions(snapshot):
            for player_id in (tx.get("adds") or {}):
                add_leagues[str(player_id)].add(str(league_key))
            for player_id in (tx.get("drops") or {}):
                drop_leagues[str(player_id)].add(str(league_key))

    player_ids = sorted(
        set(rostered_leagues)
        | set(started_leagues)
        | set(add_leagues)
        | set(drop_leagues)
    )
    players: dict[str, dict[str, Any]] = {}
    for player_id in player_ids:
        rostered = len(rostered_leagues[player_id])
        started = len(started_leagues[player_id])
        players[player_id] = {
            "player_id": player_id,
            "player": names.get(player_id, player_id),
            "rostered_leagues": rostered,
            "started_leagues": started,
            "tracked_start_rate": round(started / rostered, 4) if rostered else None,
            "added_leagues": len(add_leagues[player_id]),
            "dropped_leagues": len(drop_leagues[player_id]),
        }

    return {
        "scope": "Ironbound Network",
        "tracked_leagues": len(snapshots),
        "players": players,
        "sleeper_platform_rates": {
            "status": "UNAVAILABLE",
            "required": False,
            "note": (
                "Sleeper-wide roster/start percentages are not available from the "
                "verified public API used by this pipeline. Do not relabel tracked-"
                "league rates as Sleeper-wide."
            ),
        },
    }


def build_roster_market_report(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    beat_report: dict[str, Any] | None,
    network_context: dict[str, Any] | None,
    *,
    chronicle: ChronicleQueries | None = None,
) -> dict[str, Any]:
    players = snapshot.get("players") or {}
    team_names = _roster_team_names(snapshot)
    week = int(snapshot.get("week") or dossier.get("week") or 0)

    transaction_evidence = build_transaction_evidence(snapshot, chronicle)
    all_transactions = list(transaction_evidence.get("transactions") or [])
    normalized_current = [
        dict(tx)
        for tx in all_transactions
        if int(tx.get("week") or 0) == week
    ]

    movement_counts: Counter[str] = Counter()
    movement_kinds: dict[str, Counter[str]] = defaultdict(Counter)
    for tx in all_transactions:
        player_rows = (tx.get("players") or {}).get("all") or []
        for player in player_rows:
            player_id = str(player.get("player_id") or "")
            if not player_id:
                continue
            movement_counts[player_id] += 1
            if player.get("to_roster_id") is not None:
                movement_kinds[player_id]["adds"] += 1
            if player.get("from_roster_id") is not None:
                movement_kinds[player_id]["drops"] += 1

    repeated = [
        {
            "player_id": player_id,
            "player": _player_name(players, player_id),
            "transaction_events": count,
            "adds": movement_kinds[player_id]["adds"],
            "drops": movement_kinds[player_id]["drops"],
        }
        for player_id, count in movement_counts.items()
        if count >= 2
    ]
    repeated.sort(
        key=lambda row: (-int(row["transaction_events"]), str(row["player"]).casefold())
    )

    churn = _lineup_churn(snapshot, players, team_names, week)
    architecture = _roster_architecture(snapshot, players, team_names)
    news_timelines = _news_timelines(beat_report)
    health = dict(dossier.get("roster_health") or {})

    network = network_context or {
        "scope": "Ironbound Network",
        "tracked_leagues": 0,
        "players": {},
        "sleeper_platform_rates": {
            "status": "UNAVAILABLE",
            "required": False,
        },
    }
    network_rows = sorted(
        (
            dict(row)
            for row in (network.get("players") or {}).values()
            if row.get("added_leagues")
            or row.get("dropped_leagues")
            or row.get("started_leagues")
        ),
        key=lambda row: (
            -int(row.get("added_leagues") or 0),
            -int(row.get("started_leagues") or 0),
            str(row.get("player") or "").casefold(),
        ),
    )

    publication_context = _publication_context(snapshot)
    source_coverage = {
        key: (publication_context.get(key) or {}).get("status", "unknown")
        for key in ("transactions", "schedule")
    }
    missing_required = any(value in {"unavailable", "partial"} for value in source_coverage.values())
    return {
        "status": "MANUAL_VERIFY" if missing_required else "READY",
        "source_coverage": source_coverage,
        "week": week,
        "health": health,
        "status_timeline": _status_timeline(snapshot, beat_report, chronicle),
        "lineup_churn": churn,
        "transactions": {
            "current_week": normalized_current,
            "current_week_count": len(normalized_current),
            "season_event_count": len(all_transactions),
            "coverage": dict(transaction_evidence.get("coverage") or {}),
            "pick_provenance_status": transaction_evidence.get("pick_provenance_status"),
            "warnings": list(transaction_evidence.get("warnings") or []),
        },
        "repeated_asset_movement": repeated[:20],
        "roster_architecture": architecture,
        "news_timelines": news_timelines,
        "network_market": {
            "scope": network.get("scope") or "Ironbound Network",
            "tracked_leagues": int(network.get("tracked_leagues") or 0),
            "players": network_rows[:50],
        },
        "sleeper_platform_rates": dict(
            network.get("sleeper_platform_rates") or {
                "status": "UNAVAILABLE",
                "required": False,
            }
        ),
        "editorial_rule": (
            "Health, transactions, lineup churn, roster construction, and beat/news "
            "context may explain the same roster event. Reuse verified evidence "
            "across departments rather than treating news as a standalone silo."
        ),
    }


def _publication_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    return (
        snapshot.get("publication_sleeper")
        or snapshot.get("flagship_sleeper")
        or {}
    )


def _current_transactions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    week = str(int(snapshot.get("week") or 0))
    transactions = (_publication_context(snapshot).get("transactions") or {})
    weeks = transactions.get("weeks") or {}
    rows = []
    if isinstance(weeks, dict) and (week in weeks or int(week) in weeks):
        rows = weeks.get(week, weeks.get(int(week), []))
        return [dict(row) for row in rows or [] if isinstance(row, dict) and row.get("status") == "complete"]
    rows = snapshot.get("transactions") or []
    return [dict(row) for row in rows if isinstance(row, dict) and row.get("status") == "complete"]


def _all_transactions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    transactions = (_publication_context(snapshot).get("transactions") or {})
    weeks = transactions.get("weeks") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(weeks, dict):
        for tx_week, values in weeks.items():
            if int(tx_week) > int(snapshot.get("week") or 0):
                continue
            if isinstance(values, list):
                rows.extend(dict(row) for row in values if isinstance(row, dict) and row.get("status") == "complete")
    if not rows:
        rows.extend(_current_transactions(snapshot))
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("transaction_id") or repr(sorted(row.items())))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _normalize_transaction(
    row: dict[str, Any],
    players: dict[str, Any],
    team_names: dict[int, str],
) -> dict[str, Any]:
    settings = row.get("settings") or {}
    adds = [
        {
            "player_id": str(player_id),
            "player": _player_name(players, str(player_id)),
            "to_roster_id": _safe_int(roster_id),
            "to_team": team_names.get(_safe_int(roster_id) or 0),
        }
        for player_id, roster_id in (row.get("adds") or {}).items()
    ]
    drops = [
        {
            "player_id": str(player_id),
            "player": _player_name(players, str(player_id)),
            "from_roster_id": _safe_int(roster_id),
            "from_team": team_names.get(_safe_int(roster_id) or 0),
        }
        for player_id, roster_id in (row.get("drops") or {}).items()
    ]
    roster_ids = [
        _safe_int(value)
        for value in (row.get("roster_ids") or [])
        if _safe_int(value) is not None
    ]
    return {
        "transaction_id": row.get("transaction_id"),
        "type": row.get("type"),
        "status": row.get("status"),
        "adds": adds,
        "drops": drops,
        "roster_ids": roster_ids,
        "teams": [team_names.get(rid, f"Roster {rid}") for rid in roster_ids],
        "faab": _safe_float(
            settings.get("waiver_bid")
            if settings.get("waiver_bid") is not None
            else settings.get("amount")
        ),
        "created": row.get("created"),
    }


def _lineup_churn(
    snapshot: dict[str, Any],
    players: dict[str, Any],
    team_names: dict[int, str],
    week: int,
) -> list[dict[str, Any]]:
    current = {
        int(row.get("roster_id") or 0): {str(pid) for pid in row.get("starters") or [] if pid and str(pid) != "0"}
        for row in snapshot.get("matchups") or []
    }
    schedule = (_publication_context(snapshot).get("schedule") or {})
    weeks = schedule.get("weeks") or {}
    previous_rows = weeks.get(str(week - 1)) or weeks.get(week - 1) or []
    previous = {
        int(row.get("roster_id") or 0): {str(pid) for pid in row.get("starters") or [] if pid and str(pid) != "0"}
        for row in previous_rows
        if isinstance(row, dict)
    }
    rows = []
    for roster_id, current_starters in current.items():
        previous_starters = previous.get(roster_id)
        if previous_starters is None:
            continue
        moved_in = sorted(current_starters - previous_starters)
        moved_out = sorted(previous_starters - current_starters)
        if not moved_in and not moved_out:
            continue
        rows.append(
            {
                "roster_id": roster_id,
                "team": team_names.get(roster_id, f"Roster {roster_id}"),
                "moved_into_starting_lineup": [
                    _player_ref(players, player_id) for player_id in moved_in
                ],
                "moved_out_of_starting_lineup": [
                    _player_ref(players, player_id) for player_id in moved_out
                ],
            }
        )
    return rows


def _roster_architecture(
    snapshot: dict[str, Any],
    players: dict[str, Any],
    team_names: dict[int, str],
) -> list[dict[str, Any]]:
    rows = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        player_ids = [str(pid) for pid in roster.get("players") or []]
        positions = Counter(
            str((players.get(pid) or {}).get("position") or "UNK")
            for pid in player_ids
        )
        total = len(player_ids)
        rows.append(
            {
                "roster_id": roster_id,
                "team": team_names.get(roster_id, f"Roster {roster_id}"),
                "listed_players": total,
                "position_counts": dict(sorted(positions.items())),
                "position_shares": {
                    position: round(count / total, 4) if total else 0.0
                    for position, count in sorted(positions.items())
                },
            }
        )
    return rows


def _news_timelines(beat_report: dict[str, Any] | None) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in (beat_report or {}).get("items") or []:
        for player in item.get("league_players") or []:
            player_id = str(
                player.get("sleeper_player_id")
                or player.get("nflverse_id")
                or player.get("player")
                or ""
            )
            name = str(player.get("player") or player_id)
            if not player_id:
                continue
            grouped[(player_id, name)].append(
                {
                    "event_id": item.get("event_id"),
                    "published_at": item.get("published_at"),
                    "headline": item.get("headline") or item.get("original_title"),
                    "source": item.get("source"),
                    "source_url": item.get("source_url"),
                    "tags": list(item.get("tags") or []),
                    "editorial_lanes": dict(item.get("editorial_lanes") or {}),
                }
            )
    rows = []
    for (player_id, name), events in grouped.items():
        events.sort(key=lambda row: str(row.get("published_at") or ""))
        rows.append(
            {
                "player_id": player_id,
                "player": name,
                "events": events,
            }
        )
    rows.sort(key=lambda row: str(row["player"]).casefold())
    return rows


def _roster_team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {
        str(row.get("user_id")): row
        for row in snapshot.get("users") or []
    }
    result = {}
    for roster in snapshot.get("rosters") or []:
        rid = int(roster.get("roster_id") or 0)
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        result[rid] = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {rid}"
        )
    return result


def _player_name(players: dict[str, Any], player_id: str) -> str:
    return str((players.get(str(player_id)) or {}).get("full_name") or player_id)


def _player_ref(players: dict[str, Any], player_id: str) -> dict[str, Any]:
    row = players.get(str(player_id)) or {}
    return {
        "player_id": str(player_id),
        "player": row.get("full_name") or str(player_id),
        "position": row.get("position"),
        "nfl_team": row.get("team"),
    }


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


def _status_timeline(snapshot, beat_report, chronicle):
    window = (beat_report or {}).get("reporting_window") or {}
    if not window:
        dates = _reporting_window(snapshot)
        if dates:
            window = {"start": dates[0].isoformat(), "end": dates[1].isoformat()}
    result = {"status": "UNAVAILABLE", "events": [], "reporting_window": window,
              "source_revision": snapshot.get("chronicle_revision"),
              "note": "Observed transitions only. Polling intervals are not exact announcement times; missing history does not mean no status changes."}
    if chronicle is None:
        return result
    try:
        start, end = timestamp(window['start']), timestamp(window['end'])
    except (KeyError, ValueError, TypeError):
        return result
    tracked = {str(pid) for row in snapshot.get('rosters') or [] for pid in row.get('players') or []}
    for tx in _current_transactions(snapshot):
        tracked.update(map(str, tx.get('adds') or {}))
        tracked.update(map(str, tx.get('drops') or {}))
    for matchup in snapshot.get('matchups') or []:
        tracked.update(str(pid) for pid in matchup.get('players') or [])
    events = chronicle.player_status_events(tracked)
    selected = []
    for event in events:
        try:
            observed = timestamp(event.get('observed_at'))
        except (ValueError, TypeError):
            continue
        if start <= observed < end:
            selected.append(dict(event))
    selected.sort(key=lambda row: (timestamp(row['observed_at']), str(row.get('event_id'))))
    return {**result, 'status': 'OBSERVED_HISTORY', 'events': selected}
