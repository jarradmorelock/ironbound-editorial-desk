from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from .chronicle_events import ChronicleEvent, make_event
from .chronicle_identity import IdentityRegistry


class BackfillError(RuntimeError):
    """Raised when Sleeper historical lineage cannot be traversed safely."""


@dataclass(frozen=True)
class SeasonRef:
    league_id: str
    season: str
    name: str
    previous_league_id: str | None
    league: dict[str, Any]


@dataclass(frozen=True)
class BackfillSeasonResult:
    events: tuple[ChronicleEvent, ...]
    identity_updates: tuple[Any, ...]
    ambiguities: tuple[Any, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class BackfillRunResult:
    added_events: int
    skipped_events: int
    failed_leagues: tuple[str, ...]
    unresolved_ambiguities: tuple[Any, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MaterializeRunResult:
    failed_leagues: tuple[str, ...]
    unresolved_ambiguities: tuple[Any, ...]
    record_events_added: int


def discover_seasons(client: Any, current_league_id: str) -> list[SeasonRef]:
    current = str(current_league_id)
    seen: set[str] = set()
    newest_to_oldest: list[SeasonRef] = []
    while current:
        if current in seen:
            raise BackfillError(
                f"Sleeper previous_league_id cycle detected at league {current}"
            )
        seen.add(current)
        league = client.league(current)
        if not isinstance(league, dict):
            raise BackfillError(f"Sleeper league {current} did not return an object")
        league_id = str(league.get("league_id") or current)
        season = str(league.get("season") or "unknown")
        previous = league.get("previous_league_id")
        previous_id = str(previous).strip() if previous not in (None, "") else None
        newest_to_oldest.append(
            SeasonRef(
                league_id=league_id,
                season=season,
                name=str(league.get("name") or league_id),
                previous_league_id=previous_id,
                league=league,
            )
        )
        current = previous_id or ""
    return list(reversed(newest_to_oldest))


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


def _safe_optional(fetcher, *args) -> tuple[list[dict[str, Any]], str | None]:
    try:
        value = fetcher(*args)
        if not isinstance(value, list):
            raise ValueError("response was not a list")
        return value, None
    except (requests.RequestException, ValueError, KeyError, OSError) as exc:
        return [], str(exc)


def _historical_matchup_events(
    season_ref: SeasonRef,
    league_key: str,
    week: int,
    rows: list[dict[str, Any]],
) -> list[ChronicleEvent]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        matchup_id = row.get("matchup_id")
        if matchup_id is not None:
            grouped.setdefault(str(matchup_id), []).append(row)
    playoff_start = int(
        ((season_ref.league.get("settings") or {}).get("playoff_week_start") or 99)
    )
    events: list[ChronicleEvent] = []
    for matchup_id, sides in sorted(grouped.items()):
        if len(sides) != 2 or any(side.get("points") is None for side in sides):
            continue
        ordered = sorted(
            sides,
            key=lambda row: (
                float(row.get("points") or 0),
                int(row.get("roster_id") or 0),
            ),
            reverse=True,
        )
        top, bottom = ordered
        top_points = float(top.get("points") or 0)
        bottom_points = float(bottom.get("points") or 0)
        tie = top_points == bottom_points
        evidence = {
            "matchup_id": int(matchup_id) if matchup_id.isdigit() else matchup_id,
            "competition": "playoffs" if week >= playoff_start else "regular_season",
            "rosters": [
                {
                    "roster_id": int(side.get("roster_id") or 0),
                    "points": float(side.get("points") or 0),
                }
                for side in sorted(
                    sides, key=lambda row: int(row.get("roster_id") or 0)
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
                    f"league:{season_ref.league_id}:season:{season_ref.season}:"
                    f"week:{week}:matchup:{matchup_id}"
                ),
                league_key=league_key,
                season=season_ref.season,
                week=week,
                provenance="reconstructed_from_sleeper",
                entities={"matchup_id": evidence["matchup_id"]},
                observed_at=f"backfill:{season_ref.season}",
                evidence=evidence,
            )
        )
    return events


def _historical_transaction_events(
    season_ref: SeasonRef,
    league_key: str,
    week: int,
    rows: list[dict[str, Any]],
) -> list[ChronicleEvent]:
    events: list[ChronicleEvent] = []
    for row in rows:
        if row.get("status") != "complete":
            continue
        tx_id = str(row.get("transaction_id") or "").strip()
        if not tx_id:
            continue
        tx_type = str(row.get("type") or "").lower()
        occurred_at = _source_time(row.get("created"))
        evidence = {
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
                    season=season_ref.season,
                    week=week,
                    provenance="source_exact",
                    entities={
                        "transaction_id": tx_id,
                        "roster_ids": row.get("roster_ids") or [],
                    },
                    occurred_at=occurred_at,
                    observed_at=f"backfill:{season_ref.season}",
                    evidence=evidence,
                )
            )
            continue
        if tx_type not in {"waiver", "free_agent"}:
            continue
        add_type = "WAIVER_ADD" if tx_type == "waiver" else "FREE_AGENT_ADD"
        for player_id, roster_id in sorted((row.get("adds") or {}).items()):
            events.append(
                make_event(
                    event_type=add_type,
                    source="sleeper_transactions",
                    source_ref=f"transaction:{tx_id}:add:{player_id}",
                    league_key=league_key,
                    season=season_ref.season,
                    week=week,
                    provenance="source_exact",
                    entities={
                        "transaction_id": tx_id,
                        "player_id": str(player_id),
                        "roster_id": roster_id,
                    },
                    occurred_at=occurred_at,
                    observed_at=f"backfill:{season_ref.season}",
                    evidence=evidence,
                )
            )
        for player_id, roster_id in sorted((row.get("drops") or {}).items()):
            events.append(
                make_event(
                    event_type="DROP",
                    source="sleeper_transactions",
                    source_ref=f"transaction:{tx_id}:drop:{player_id}",
                    league_key=league_key,
                    season=season_ref.season,
                    week=week,
                    provenance="source_exact",
                    entities={
                        "transaction_id": tx_id,
                        "player_id": str(player_id),
                        "roster_id": roster_id,
                    },
                    occurred_at=occurred_at,
                    observed_at=f"backfill:{season_ref.season}",
                    evidence=evidence,
                )
            )
    return events


def _pick_identity(row: dict[str, Any]) -> str:
    return ":".join(
        str(row.get(key) if row.get(key) is not None else "")
        for key in ("season", "round", "roster_id", "owner_id", "previous_owner_id")
    )


def _identity_rows(
    users: list[dict[str, Any]], rosters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    users_by_id = {str(user.get("user_id")): user for user in users}
    rows: list[dict[str, Any]] = []
    for roster in rosters:
        owner_id = str(roster.get("owner_id") or "")
        user = users_by_id.get(owner_id) or {}
        metadata = user.get("metadata") or {}
        rows.append(
            {
                "roster_id": int(roster["roster_id"]),
                "owner_id": owner_id,
                "team_name": metadata.get("team_name") or user.get("display_name"),
                "manager_name": user.get("display_name"),
            }
        )
    return rows


def backfill_season(
    client: Any,
    season_ref: SeasonRef,
    league_config: Any,
    registry: IdentityRegistry,
    *,
    max_final_week: int | None = None,
) -> BackfillSeasonResult:
    league_key = str(league_config.key)
    warnings: list[str] = []
    events: list[ChronicleEvent] = []

    users = client.users(season_ref.league_id)
    rosters = client.rosters(season_ref.league_id)
    if not isinstance(users, list) or not isinstance(rosters, list):
        raise BackfillError("Sleeper users/rosters response was invalid")
    rows = _identity_rows(users, rosters)
    if str(league_config.league_format).casefold() == "dynasty":
        identity_result = registry.bootstrap_dynasty_season(
            league_key=league_key,
            season=season_ref.season,
            rosters=rows,
        )
        identity_updates: tuple[Any, ...] = identity_result.mappings
        ambiguities: tuple[Any, ...] = identity_result.ambiguities
    else:
        identity_updates = registry.bootstrap_redraft_season(
            league_key=league_key,
            season=season_ref.season,
            rosters=rows,
        )
        ambiguities = ()

    for week in range(1, 19):
        if max_final_week is None or week <= max_final_week:
            matchup_rows, matchup_error = _safe_optional(
                client.matchups, season_ref.league_id, week
            )
            if matchup_error:
                warnings.append(f"week {week} matchups: {matchup_error}")
            events.extend(
                _historical_matchup_events(season_ref, league_key, week, matchup_rows)
            )
        transaction_rows, transaction_error = _safe_optional(
            client.transactions, season_ref.league_id, week
        )
        if transaction_error:
            warnings.append(f"week {week} transactions: {transaction_error}")
        events.extend(
            _historical_transaction_events(
                season_ref, league_key, week, transaction_rows
            )
        )

    drafts, draft_error = _safe_optional(client.drafts, season_ref.league_id)
    if draft_error:
        warnings.append(f"drafts: {draft_error}")
    for draft in drafts:
        draft_id = str(draft.get("draft_id") or "").strip()
        if not draft_id:
            continue
        picks, picks_error = _safe_optional(client.draft_picks, draft_id)
        if picks_error:
            warnings.append(f"draft {draft_id} picks: {picks_error}")
        for pick in picks:
            pick_no = pick.get("pick_no")
            events.append(
                make_event(
                    event_type="DRAFT_PICK",
                    source="sleeper_draft_picks",
                    source_ref=f"draft:{draft_id}:pick:{pick_no}",
                    league_key=league_key,
                    season=season_ref.season,
                    week=None,
                    provenance="source_exact",
                    entities={
                        "draft_id": draft_id,
                        "pick_no": pick_no,
                        "round": pick.get("round"),
                        "roster_id": pick.get("roster_id"),
                        "player_id": pick.get("player_id"),
                    },
                    observed_at=f"backfill:{season_ref.season}",
                    evidence={"draft": draft, "pick": pick},
                )
            )
        draft_traded, traded_error = _safe_optional(
            client.draft_traded_picks, draft_id
        )
        if traded_error:
            warnings.append(f"draft {draft_id} traded picks: {traded_error}")
        for pick in draft_traded:
            identity = _pick_identity(pick)
            events.append(
                make_event(
                    event_type="TRADED_PICK",
                    source="sleeper_traded_picks",
                    source_ref=f"traded-pick:{identity}",
                    league_key=league_key,
                    season=season_ref.season,
                    week=None,
                    provenance="source_exact",
                    entities={"draft_id": draft_id, **pick},
                    observed_at=f"backfill:{season_ref.season}",
                    evidence=pick,
                )
            )

    league_traded, traded_error = _safe_optional(
        client.traded_picks, season_ref.league_id
    )
    if traded_error:
        warnings.append(f"league traded picks: {traded_error}")
    for pick in league_traded:
        identity = _pick_identity(pick)
        events.append(
            make_event(
                event_type="TRADED_PICK",
                source="sleeper_traded_picks",
                source_ref=f"traded-pick:{identity}",
                league_key=league_key,
                season=season_ref.season,
                week=None,
                provenance="source_exact",
                entities=dict(pick),
                observed_at=f"backfill:{season_ref.season}",
                evidence=pick,
            )
        )

    for bracket_name, fetcher in (
        ("winners", client.winners_bracket),
        ("losers", client.losers_bracket),
    ):
        bracket_rows, error = _safe_optional(fetcher, season_ref.league_id)
        if error:
            warnings.append(f"{bracket_name} bracket: {error}")
        for row in bracket_rows:
            events.append(
                make_event(
                    event_type="PLAYOFF_BRACKET_RESULT",
                    source="sleeper_bracket",
                    source_ref=(
                        f"league:{season_ref.league_id}:bracket:{bracket_name}:"
                        f"round:{row.get('r')}:match:{row.get('m')}"
                    ),
                    league_key=league_key,
                    season=season_ref.season,
                    week=None,
                    provenance="reconstructed_from_sleeper",
                    entities={
                        "bracket": bracket_name,
                        "round": row.get("r"),
                        "match": row.get("m"),
                    },
                    observed_at=f"backfill:{season_ref.season}",
                    evidence=row,
                )
            )

    deduped = {event.event_id: event for event in events}
    return BackfillSeasonResult(
        events=tuple(deduped[key] for key in sorted(deduped)),
        identity_updates=identity_updates,
        ambiguities=ambiguities,
        warnings=tuple(warnings),
    )


def _current_season_limit(
    client: Any, newest_season: str
) -> tuple[str | None, int | None, str | None]:
    try:
        state = client.nfl_state()
        current_season = str(state.get("season") or "")
        current_week = int(state.get("week") or 0)
        return current_season, max(current_week - 1, 0), None
    except (requests.RequestException, ValueError, TypeError, KeyError, OSError) as exc:
        # If current NFL state cannot be established, preserve exact transactions but
        # do not manufacture finals for the newest season.
        return str(newest_season), 0, str(exc)


def run_materialize(store: Any) -> MaterializeRunResult:
    from .chronicle_materialize import materialize_league

    registry = store.read_identity_registry()
    backfill_coverage = store.read_backfill_coverage()
    failed: list[str] = []
    unresolved: list[Any] = []
    record_added = 0
    league_keys = tuple(sorted(set(store.league_keys()) | set(registry.league_keys())))
    for league_key in league_keys:
        ambiguities = registry.unresolved_for_league(league_key)
        if ambiguities:
            failed.append(league_key)
            unresolved.extend(ambiguities)
            continue
        events = store.read_all_league_events(league_key)
        if not events:
            continue
        history = materialize_league(
            events,
            registry,
            coverage_warnings=(
                (backfill_coverage.get(league_key) or {}).get("warnings") or ()
            ),
        )
        record_result = store.append_events(history.record_events)
        record_added += record_result.added
        store.write_materialized_history(history)
    return MaterializeRunResult(
        failed_leagues=tuple(sorted(failed)),
        unresolved_ambiguities=tuple(unresolved),
        record_events_added=record_added,
    )


def run_backfill(
    leagues: Iterable[Any],
    client: Any,
    store: Any,
) -> BackfillRunResult:
    registry = store.read_identity_registry()
    backfill_coverage = store.read_backfill_coverage()
    added = 0
    skipped = 0
    failed: list[str] = []
    warnings: list[str] = []
    unresolved: list[Any] = []

    configs = list(leagues)
    discovered: dict[str, list[SeasonRef]] = {}
    for config in configs:
        key = str(config.key)
        try:
            discovered[key] = discover_seasons(client, str(config.sleeper_league_id))
        except (BackfillError, requests.RequestException, ValueError, KeyError, OSError) as exc:
            discovered[key] = []
            failed.append(key)
            warnings.append(f"{key}: {exc}")

    newest = max(
        (season.season for seasons in discovered.values() for season in seasons),
        default="",
    )
    current_season, completed_week, state_warning = _current_season_limit(client, newest)
    if state_warning:
        warnings.append(f"nfl state unavailable: {state_warning}")

    for config in configs:
        league_key = str(config.key)
        seasons = discovered.get(league_key) or []
        if not seasons:
            continue
        try:
            league_warnings: list[str] = []
            for season_ref in seasons:
                max_final_week = (
                    completed_week
                    if current_season and season_ref.season == current_season
                    else None
                )
                result = backfill_season(
                    client,
                    season_ref,
                    config,
                    registry,
                    max_final_week=max_final_week,
                )
                append_result = store.append_events(result.events)
                added += append_result.added
                skipped += append_result.skipped
                league_warnings.extend(
                    f"{league_key} {season_ref.season}: {warning}"
                    for warning in result.warnings
                )
                unresolved.extend(result.ambiguities)
            backfill_coverage[league_key] = {
                "seasons": [season.season for season in seasons],
                "warnings": sorted(set(league_warnings)),
            }
            store.write_backfill_coverage(backfill_coverage)
            store.write_identity_registry(registry)
            warnings.extend(league_warnings)
            if registry.unresolved_for_league(league_key):
                failed.append(league_key)
                continue

            from .chronicle_materialize import materialize_league

            history = materialize_league(
                store.read_all_league_events(league_key),
                registry,
                coverage_warnings=league_warnings,
            )
            record_result = store.append_events(history.record_events)
            added += record_result.added
            skipped += record_result.skipped
            store.write_materialized_history(history)
        except (
            BackfillError,
            requests.RequestException,
            ValueError,
            KeyError,
            OSError,
        ) as exc:
            failed.append(league_key)
            warnings.append(f"{league_key}: {exc}")

    store.write_identity_registry(registry)
    return BackfillRunResult(
        added_events=added,
        skipped_events=skipped,
        failed_leagues=tuple(sorted(set(failed))),
        unresolved_ambiguities=tuple(unresolved or registry.unresolved_ambiguities()),
        warnings=tuple(warnings),
    )
