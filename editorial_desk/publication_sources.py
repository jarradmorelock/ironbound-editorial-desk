from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .external_inputs import ExternalEditorialInputs


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _history(snapshot: dict[str, Any]) -> dict[str, Any]:
    return snapshot.get("publication_sleeper") or snapshot.get("flagship_sleeper") or {}


def _week_keys(section: dict[str, Any]) -> list[int]:
    weeks = section.get("weeks") or {}
    values: list[int] = []
    if isinstance(weeks, dict):
        for key in weeks:
            try:
                values.append(int(key))
            except (TypeError, ValueError):
                continue
    return sorted(values)


def build_source_manifest(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    external: ExternalEditorialInputs,
    *,
    beat_report: dict[str, Any] | None,
    publication_assets: dict[str, Any] | None,
    information_cutoff: str | None = None,
) -> dict[str, Any]:
    history = _history(snapshot)
    schedule = history.get("schedule") or {}
    transactions = history.get("transactions") or {}
    projection = ((snapshot.get("ranking_inputs") or {}).get("sleeper_projections") or {})
    nfl = snapshot.get("nfl_context") or {}

    ranking_metadata = dict(external.source_metadata or {})
    ranking_ready = bool(
        external.official_power_rankings
        or external.schema_version >= 3
        and ranking_metadata.get("ranking_week") is not None
    )

    assets = publication_assets or external.publication_assets or {}
    asset_rows = {
        key: dict(assets.get(key) or {})
        for key in ("power_rankings", "playoff_forecast")
    }
    assets_ready = bool(asset_rows) and all(
        str(row.get("status") or "").upper() == "READY"
        and bool(row.get("package_path"))
        for row in asset_rows.values()
    )

    beat_status_raw = str((beat_report or {}).get("status") or "NOT_CONFIGURED").upper()
    if beat_status_raw == "READY":
        beat_status = "READY"
    elif beat_status_raw in {"PARTIAL", "PARTIAL_HISTORY"}:
        beat_status = "PARTIAL"
    elif beat_status_raw == "NOT_CONFIGURED":
        beat_status = "NOT_CONFIGURED"
    else:
        beat_status = "UNAVAILABLE"

    cutoff = (
        information_cutoff
        or dossier.get("information_current_through")
        or snapshot.get("collected_at")
    )

    return {
        "information_cutoff": cutoff,
        "sleeper": {
            "matchups": {
                "status": str(schedule.get("status") or "unknown").upper(),
                "weeks": _week_keys(schedule),
                "errors": dict(schedule.get("errors") or {}),
            },
            "transactions": {
                "status": str(transactions.get("status") or "unknown").upper(),
                "weeks": _week_keys(transactions),
                "errors": dict(transactions.get("errors") or {}),
            },
            "projections": {
                "status": str(projection.get("status") or "unknown").upper(),
                "season": projection.get("season"),
                "week": projection.get("week"),
                "player_count": len(projection.get("players") or {}),
            },
        },
        "nflverse": {
            key: {
                "status": str((nfl.get(key) or {}).get("status") or "unknown").upper(),
                "record_count": len((nfl.get(key) or {}).get("records") or []),
            }
            for key in (
                "player_stats",
                "season_player_stats",
                "snap_counts",
                "play_by_play",
                "injuries",
                "schedule",
            )
        },
        "rankings": {
            "status": "READY" if ranking_ready else "UNAVAILABLE",
            "schema_version": external.schema_version,
            "results_through_week": ranking_metadata.get("results_through_week"),
            "ranking_week": ranking_metadata.get("ranking_week"),
            "authority": "Ironbound_power_ranks",
        },
        "publication_assets": {
            "status": "READY" if assets_ready else "UNAVAILABLE",
            "assets": asset_rows,
        },
        "beat_news": {
            "status": beat_status,
            "blocking": False,
            "coverage_start": ((beat_report or {}).get("coverage") or {}).get("durable_since"),
            "source_revision": (beat_report or {}).get("source_revision"),
            "ledger_manifest": (beat_report or {}).get("ledger_manifest") or {},
        },
    }


def health_evidence(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    beat_report: dict[str, Any] | None,
    information_cutoff: str | None,
) -> dict[str, Any]:
    cutoff_text = (
        information_cutoff
        or dossier.get("information_current_through")
        or snapshot.get("collected_at")
    )
    cutoff = _parse_time(cutoff_text)

    reserve_map: dict[str, dict[str, Any]] = {}
    team_names: dict[int, str] = {}
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    for roster in snapshot.get("rosters") or []:
        rid = int(roster.get("roster_id") or 0)
        user = users.get(str(roster.get("owner_id"))) or {}
        metadata = user.get("metadata") or {}
        team_names[rid] = str(metadata.get("team_name") or user.get("display_name") or f"Roster {rid}")
        active = {str(v) for v in roster.get("players") or []}
        reserve = {str(v) for v in roster.get("reserve") or []}
        taxi = {str(v) for v in roster.get("taxi") or []}
        for player_id in active | reserve | taxi:
            reserve_map[player_id] = {
                "roster_id": rid,
                "fantasy_team": team_names[rid],
                "on_ir": player_id in reserve,
                "on_taxi": player_id in taxi,
            }

    raw_health = dossier.get("roster_health") or {}
    players: list[dict[str, Any]] = []
    for row in raw_health.get("players") or []:
        observed = _parse_time(row.get("observed_at"))
        if cutoff is not None and observed is not None and observed > cutoff:
            continue
        player_id = str(row.get("player_id") or "")
        context = reserve_map.get(player_id) or {}
        players.append(
            {
                **dict(row),
                **{key: value for key, value in context.items() if row.get(key) is None},
                "observed_at": row.get("observed_at") or dossier.get("information_current_through") or snapshot.get("collected_at"),
            }
        )

    players.sort(
        key=lambda row: (
            str(row.get("team") or row.get("fantasy_team") or "").casefold(),
            str(row.get("player") or row.get("player_id") or "").casefold(),
        )
    )

    news_events: list[dict[str, Any]] = []
    for item in (beat_report or {}).get("items") or []:
        lanes = item.get("editorial_lanes") or {}
        if not lanes.get("health_context"):
            continue
        published = _parse_time(item.get("published_at"))
        if cutoff is not None and published is not None and published > cutoff:
            continue
        news_events.append(dict(item))
    news_events.sort(key=lambda row: (str(row.get("published_at") or ""), str(row.get("event_id") or "")))

    raw_status = str(raw_health.get("status") or "unknown").lower()
    if raw_status in {"available", "ready"}:
        status = "READY" if players or news_events else "READY_NO_ITEMS"
    elif players or news_events:
        status = "PARTIAL"
    else:
        status = "UNAVAILABLE"

    return {
        "status": status,
        "information_cutoff": cutoff_text,
        "players": players,
        "news_events": news_events,
        "source_status": raw_health.get("status"),
    }
