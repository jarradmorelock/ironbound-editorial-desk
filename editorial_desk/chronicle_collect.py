from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable

import requests

from .chronicle_events import ChronicleEvent, make_event
from .chronicle_store import ChronicleStore


def _source_time(value: Any) -> str | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number > 10_000_000_000:
        number /= 1000.0
    return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()


def _health_state(player: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": player.get("status"),
        "injury_status": player.get("injury_status"),
    }


def _league_state(
    league: dict[str, Any],
    users: list[dict[str, Any]],
    rosters: list[dict[str, Any]],
    matchups: list[dict[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    return {
        "observed_at": observed_at,
        "league": {
            "league_id": league.get("league_id"),
            "season": league.get("season"),
        },
        "users": users,
        "rosters": {
            str(row.get("roster_id")): {
                "owner_id": row.get("owner_id"),
                "players": sorted(str(v) for v in row.get("players") or []),
                "reserve": sorted(str(v) for v in row.get("reserve") or []),
                "taxi": sorted(str(v) for v in row.get("taxi") or []),
            }
            for row in rosters
        },
        "lineups": {
            str(row.get("roster_id")): sorted(
                str(v) for v in row.get("starters") or []
            )
            for row in matchups
        },
    }


def _normalize_transactions(
    league_key: str,
    season: str,
    week: int,
    transactions: list[dict[str, Any]],
    observed_at: str,
) -> list[ChronicleEvent]:
    events: list[ChronicleEvent] = []
    for row in transactions:
        if row.get("status") != "complete":
            continue
        tx_id = str(row.get("transaction_id") or "").strip()
        if not tx_id:
            continue
        tx_type = str(row.get("type") or "").lower()
        occurred_at = _source_time(row.get("created"))
        common_evidence = {
            "transaction_id": tx_id,
            "type": tx_type,
            "roster_ids": row.get("roster_ids") or [],
            "adds": row.get("adds") or {},
            "drops": row.get("drops") or {},
            "settings": row.get("settings") or {},
        }
        if tx_type == "trade":
            events.append(
                make_event(
                    event_type="TRADE",
                    source="sleeper_transactions",
                    source_ref=f"transaction:{tx_id}",
                    league_key=league_key,
                    season=season,
                    week=week,
                    provenance="source_exact",
                    entities={
                        "transaction_id": tx_id,
                        "roster_ids": row.get("roster_ids") or [],
                    },
                    occurred_at=occurred_at,
                    observed_at=observed_at,
                    evidence=common_evidence,
                )
            )
            continue
        add_type = "WAIVER_ADD" if tx_type == "waiver" else "FREE_AGENT_ADD"
        for player_id, roster_id in sorted((row.get("adds") or {}).items()):
            events.append(
                make_event(
                    event_type=add_type,
                    source="sleeper_transactions",
                    source_ref=f"transaction:{tx_id}:add:{player_id}",
                    league_key=league_key,
                    season=season,
                    week=week,
                    provenance="source_exact",
                    entities={
                        "transaction_id": tx_id,
                        "player_id": str(player_id),
                        "roster_id": roster_id,
                    },
                    occurred_at=occurred_at,
                    observed_at=observed_at,
                    evidence=common_evidence,
                )
            )
        for player_id, roster_id in sorted((row.get("drops") or {}).items()):
            events.append(
                make_event(
                    event_type="DROP",
                    source="sleeper_transactions",
                    source_ref=f"transaction:{tx_id}:drop:{player_id}",
                    league_key=league_key,
                    season=season,
                    week=week,
                    provenance="source_exact",
                    entities={
                        "transaction_id": tx_id,
                        "player_id": str(player_id),
                        "roster_id": roster_id,
                    },
                    occurred_at=occurred_at,
                    observed_at=observed_at,
                    evidence=common_evidence,
                )
            )
    return events


def _normalize_reserve_changes(
    league_key: str,
    season: str,
    week: int,
    previous: dict[str, Any],
    current: dict[str, Any],
    observed_at: str,
) -> list[ChronicleEvent]:
    previous_rosters = previous.get("rosters") or {}
    if not previous_rosters:
        return []
    prior_time = previous.get("observed_at")
    events: list[ChronicleEvent] = []
    for roster_id, row in (current.get("rosters") or {}).items():
        before = set((previous_rosters.get(roster_id) or {}).get("reserve") or [])
        after = set(row.get("reserve") or [])
        for player_id in sorted(before ^ after):
            events.append(
                make_event(
                    event_type="IR_RESERVE_CHANGE",
                    source="sleeper_rosters",
                    source_ref=f"roster:{roster_id}:reserve:{player_id}",
                    league_key=league_key,
                    season=season,
                    week=week,
                    provenance="observed_live",
                    entities={
                        "roster_id": int(roster_id),
                        "player_id": player_id,
                    },
                    before={"on_reserve": player_id in before},
                    after={"on_reserve": player_id in after},
                    observed_at=observed_at,
                    observed_before=prior_time,
                    observed_after=observed_at,
                )
            )
    return events


def _normalize_lineup_changes(
    league_key: str,
    season: str,
    week: int,
    previous: dict[str, Any],
    current: dict[str, Any],
    observed_at: str,
) -> list[ChronicleEvent]:
    previous_lineups = previous.get("lineups") or {}
    if not previous_lineups:
        return []
    prior_time = previous.get("observed_at")
    events: list[ChronicleEvent] = []
    for roster_id, after in (current.get("lineups") or {}).items():
        before = previous_lineups.get(roster_id)
        if before is None or before == after:
            continue
        events.append(
            make_event(
                event_type="LINEUP_CHANGE",
                source="sleeper_matchups",
                source_ref=f"roster:{roster_id}:lineup",
                league_key=league_key,
                season=season,
                week=week,
                provenance="observed_live",
                entities={"roster_id": int(roster_id)},
                before={"starters": before},
                after={"starters": after},
                observed_at=observed_at,
                observed_before=prior_time,
                observed_after=observed_at,
            )
        )
    return events


def _normalize_matchup_finals(
    league_key: str,
    season: str,
    week: int,
    matchups: list[dict[str, Any]],
    observed_at: str,
) -> list[ChronicleEvent]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in matchups:
        matchup_id = row.get("matchup_id")
        if matchup_id is None:
            continue
        grouped.setdefault(str(matchup_id), []).append(row)
    events: list[ChronicleEvent] = []
    for matchup_id, sides in sorted(grouped.items()):
        if len(sides) != 2:
            continue
        ordered = sorted(
            sides,
            key=lambda r: (
                float(r.get("points") or 0),
                int(r.get("roster_id") or 0),
            ),
            reverse=True,
        )
        top, bottom = ordered
        top_points = float(top.get("points") or 0)
        bottom_points = float(bottom.get("points") or 0)
        tie = top_points == bottom_points
        evidence = {
            "matchup_id": int(matchup_id) if matchup_id.isdigit() else matchup_id,
            "rosters": [
                {
                    "roster_id": int(row.get("roster_id") or 0),
                    "points": float(row.get("points") or 0),
                }
                for row in sorted(
                    sides, key=lambda r: int(r.get("roster_id") or 0)
                )
            ],
            "winner_roster_id": None if tie else int(top.get("roster_id") or 0),
            "loser_roster_id": None if tie else int(bottom.get("roster_id") or 0),
            "tie": tie,
        }
        events.append(
            make_event(
                event_type="MATCHUP_FINAL",
                source="sleeper_matchups",
                source_ref=(
                    f"league:{league_key}:season:{season}:week:{week}:"
                    f"matchup:{matchup_id}"
                ),
                league_key=league_key,
                season=season,
                week=week,
                provenance="source_exact",
                entities={"matchup_id": evidence["matchup_id"]},
                observed_at=observed_at,
                evidence=evidence,
            )
        )
    return events


def _status_events(
    season: str,
    week: int,
    players: dict[str, Any],
    tracked_ids: set[str],
    previous: dict[str, Any],
    observed_at: str,
) -> tuple[list[ChronicleEvent], dict[str, Any]]:
    previous_players = previous.get("players") or {}
    previous_time = previous.get("observed_at")
    current_players = {
        player_id: _health_state(players.get(player_id) or {})
        for player_id in sorted(tracked_ids)
        if player_id in players
    }
    events: list[ChronicleEvent] = []
    if previous_players:
        for player_id, after in current_players.items():
            before = previous_players.get(player_id)
            if before is None or before == after:
                continue
            events.append(
                make_event(
                    event_type="PLAYER_STATUS_CHANGE",
                    source="sleeper_players",
                    source_ref=f"player:{player_id}:status",
                    league_key=None,
                    season=season,
                    week=week,
                    provenance="observed_live",
                    entities={"player_id": player_id},
                    before=before,
                    after=after,
                    observed_at=observed_at,
                    observed_before=previous_time,
                    observed_after=observed_at,
                    cross_league_key=f"nfl-player:{player_id}",
                )
            )
    return events, {"observed_at": observed_at, "players": current_players}


def _mark_first_success(
    store: ChronicleStore,
    *,
    scope: str,
    source: str,
    observed_at: str,
) -> None:
    coverage = store.read_coverage()
    if scope == "global":
        bucket = coverage.setdefault("global", {})
    else:
        leagues = coverage.setdefault("leagues", {})
        bucket = leagues.setdefault(scope, {})
    source_row = bucket.setdefault(source, {})
    if "first_success" not in source_row:
        source_row["first_success"] = observed_at
        store.write_coverage(coverage)


def collect_pulse(
    leagues: Iterable[Any],
    client: Any,
    store: ChronicleStore,
    week: int,
    observed_at: str,
    *,
    finalize_matchups: bool = False,
) -> dict[str, Any]:
    state = client.nfl_state()
    season = str(state.get("season") or "unknown")
    run_id = hashlib.sha256(
        f"{observed_at}|{season}|{week}|{finalize_matchups}".encode()
    ).hexdigest()[:16]
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "observed_at": observed_at,
        "season": season,
        "week": week,
        "finalize_matchups": finalize_matchups,
        "source_freshness": {},
        "leagues": {},
        "event_counts": {"added": 0, "skipped": 0},
        "warnings": [],
    }

    previous_global = store.read_current_state("global_players")
    try:
        players = client.players()
        if not isinstance(players, dict):
            raise ValueError("Sleeper player directory was not an object")
        player_freshness = "fresh"
    except (requests.RequestException, ValueError, KeyError, OSError) as exc:
        players = None
        player_freshness = "stale" if previous_global else "unavailable"
        manifest["warnings"].append(f"player health: {exc}")
    manifest["source_freshness"]["player_health"] = player_freshness

    tracked_ids: set[str] = set()

    for league_config in leagues:
        key = str(league_config.key)
        league_id = str(league_config.sleeper_league_id)
        try:
            league = client.league(league_id)
            users = client.users(league_id)
            rosters = client.rosters(league_id)
            matchups = client.matchups(league_id, week)
            transactions = client.transactions(league_id, week)
            previous = store.read_current_state(f"league-{key}")
            current = _league_state(
                league, users, rosters, matchups, observed_at
            )
            for roster in rosters:
                tracked_ids.update(str(v) for v in roster.get("players") or [])
                tracked_ids.update(str(v) for v in roster.get("reserve") or [])
                tracked_ids.update(str(v) for v in roster.get("taxi") or [])
            for matchup in matchups:
                tracked_ids.update(str(v) for v in matchup.get("players") or [])
                tracked_ids.update(str(v) for v in matchup.get("starters") or [])
            for tx in transactions:
                tracked_ids.update(str(v) for v in (tx.get("adds") or {}))
                tracked_ids.update(str(v) for v in (tx.get("drops") or {}))

            events = _normalize_transactions(
                key, season, week, transactions, observed_at
            )
            events += _normalize_reserve_changes(
                key, season, week, previous, current, observed_at
            )
            events += _normalize_lineup_changes(
                key, season, week, previous, current, observed_at
            )
            if finalize_matchups:
                events += _normalize_matchup_finals(
                    key, season, week, matchups, observed_at
                )
            result = store.append_events(events)
            store.write_current_state(f"league-{key}", current)
            _mark_first_success(
                store,
                scope=key,
                source="lineups",
                observed_at=observed_at,
            )
            _mark_first_success(
                store,
                scope=key,
                source="reserve",
                observed_at=observed_at,
            )
            manifest["event_counts"]["added"] += result.added
            manifest["event_counts"]["skipped"] += result.skipped
            manifest["leagues"][key] = {"status": "fresh", "error": None}
        except (requests.RequestException, ValueError, KeyError, OSError) as exc:
            manifest["leagues"][key] = {
                "status": "unavailable",
                "error": str(exc),
            }

    if players is not None:
        status_events, current_global = _status_events(
            season,
            week,
            players,
            tracked_ids,
            previous_global,
            observed_at,
        )
        result = store.append_events(status_events)
        store.write_current_state("global_players", current_global)
        _mark_first_success(
            store,
            scope="global",
            source="player_health",
            observed_at=observed_at,
        )
        manifest["event_counts"]["added"] += result.added
        manifest["event_counts"]["skipped"] += result.skipped

    store.write_manifest(run_id, manifest)
    return manifest
