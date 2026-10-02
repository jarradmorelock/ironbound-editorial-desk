from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .external_inputs import ExternalEditorialInputs


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    parsed = _timestamp(value)
    return parsed.isoformat() if parsed else None


def _status(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    if raw in {"available", "ready", "complete", "ok"}:
        return "READY"
    if raw in {"partial", "partial_history", "manual_verify", "degraded"}:
        return "PARTIAL"
    if raw in {"not_applicable", "n/a"}:
        return "NOT_APPLICABLE"
    return "UNAVAILABLE"


def _publication_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    return (
        snapshot.get("publication_sleeper")
        or snapshot.get("flagship_sleeper")
        or {}
    )


def _sorted_week_keys(value: Any) -> list[int]:
    result: list[int] = []
    if not isinstance(value, dict):
        return result
    for key in value:
        try:
            result.append(int(key))
        except (TypeError, ValueError):
            continue
    return sorted(set(result))


def _cutoff(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    explicit: str | None,
) -> str | None:
    for value in (
        explicit,
        dossier.get("information_current_through"),
        snapshot.get("collected_at"),
    ):
        normalized = _iso(value)
        if normalized:
            return normalized
    return None


def _before_or_at(value: Any, cutoff: datetime | None) -> bool:
    if cutoff is None:
        return True
    observed = _timestamp(value)
    # Rows without their own timestamp are evidence from the dossier/snapshot
    # that owns the explicit information cutoff.
    return observed is None or observed <= cutoff


def health_evidence(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    beat_report: dict[str, Any] | None,
    information_cutoff: str | None,
) -> dict[str, Any]:
    cutoff_iso = _cutoff(snapshot, dossier, information_cutoff)
    cutoff = _timestamp(cutoff_iso)

    health = dossier.get("roster_health") or {}
    raw_players = (
        health.get("players")
        if isinstance(health, dict)
        else health
    ) or []

    by_player: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    for raw in raw_players:
        if not isinstance(raw, dict):
            continue
        observed = (
            raw.get("observed_at")
            or raw.get("updated_at")
            or raw.get("collected_at")
        )
        if not _before_or_at(observed, cutoff):
            continue
        row = dict(raw)
        player_id = str(
            row.get("player_id")
            or row.get("sleeper_player_id")
            or ""
        )
        row["observed_at"] = _iso(observed) or cutoff_iso
        row["evidence_status"] = "VERIFIED_AT_CUTOFF"
        if player_id:
            row["player_id"] = player_id
            previous = by_player.get(player_id)
            previous_time = _timestamp((previous or {}).get("observed_at"))
            current_time = _timestamp(row.get("observed_at"))
            if (
                previous is None
                or previous_time is None
                or (
                    current_time is not None
                    and current_time >= previous_time
                )
            ):
                by_player[player_id] = row
        else:
            anonymous.append(row)

    events: list[dict[str, Any]] = []
    for raw in (beat_report or {}).get("items") or []:
        if not isinstance(raw, dict):
            continue
        lanes = raw.get("editorial_lanes") or {}
        if not lanes.get("health_context"):
            continue
        published = raw.get("published_at") or raw.get("accepted_at")
        if not _before_or_at(published, cutoff):
            continue
        events.append(
            {
                "event_id": raw.get("event_id"),
                "published_at": _iso(published)
                or str(published or ""),
                "headline": raw.get("headline")
                or raw.get("original_title"),
                "source": raw.get("source"),
                "source_url": raw.get("source_url"),
                "league_players": [
                    dict(row)
                    for row in raw.get("league_players") or []
                    if isinstance(row, dict)
                ],
            }
        )
    events.sort(
        key=lambda row: (
            str(row.get("published_at") or ""),
            str(row.get("event_id") or ""),
        )
    )

    players = sorted(
        [*by_player.values(), *anonymous],
        key=lambda row: (
            str(row.get("team") or row.get("fantasy_team") or "").casefold(),
            str(row.get("player") or row.get("player_id") or "").casefold(),
        ),
    )

    return {
        "status": _status(
            health.get("status") if isinstance(health, dict) else "available"
        ),
        "information_cutoff": cutoff_iso,
        "players": players,
        "news_events": events,
        "source_status": (
            health.get("source_status")
            if isinstance(health, dict)
            else None
        ),
    }


def build_source_manifest(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    external: ExternalEditorialInputs,
    *,
    beat_report: dict[str, Any] | None,
    publication_assets: dict[str, Any] | None,
    information_cutoff: str | None = None,
) -> dict[str, Any]:
    cutoff_iso = _cutoff(snapshot, dossier, information_cutoff)
    context = _publication_context(snapshot)

    schedule = context.get("schedule") or {}
    transactions = context.get("transactions") or {}
    projections = (
        (snapshot.get("ranking_inputs") or {}).get("sleeper_projections")
        or {}
    )

    nfl_context = snapshot.get("nfl_context") or {}
    nflverse: dict[str, dict[str, Any]] = {}
    for key in (
        "schedule",
        "player_stats",
        "injuries",
        "noteworthy_late_plays",
        "snap_counts",
        "play_by_play",
    ):
        row = nfl_context.get(key) or {}
        nflverse[key] = {
            "status": _status(row.get("status")),
            "error": row.get("error"),
        }

    beat = beat_report or {}
    beat_coverage = beat.get("coverage") or {}
    beat_status = _status(beat.get("status"))
    beat_blocking = beat_status == "UNAVAILABLE"
    warnings: list[dict[str, Any]] = []
    if beat_status == "PARTIAL":
        warnings.append(
            {
                "source": "beat_news",
                "code": "PARTIAL_HISTORY",
                "detail": beat.get("error")
                or beat_coverage.get("note")
                or "Beat/news history is incomplete for the reporting window.",
            }
        )
    elif beat_status == "UNAVAILABLE":
        warnings.append(
            {
                "source": "beat_news",
                "code": "UNAVAILABLE",
                "detail": beat.get("error")
                or "Beat/news source is unavailable.",
            }
        )

    assets = {
        key: dict(value)
        for key, value in (publication_assets or {}).items()
        if isinstance(value, dict)
    }

    metadata = dict(external.source_metadata or {})
    rankings_ready = bool(
        external.official_power_rankings
        or external.playoff_odds
        or external.remaining_schedule_strength
        or external.weekly_matchup_forecast
        or assets
    )

    return {
        "schema_version": 1,
        "information_cutoff": cutoff_iso,
        "sleeper": {
            "matchups": {
                "status": _status(schedule.get("status")),
                "weeks": _sorted_week_keys(schedule.get("weeks")),
                "errors": dict(schedule.get("errors") or {}),
            },
            "transactions": {
                "status": _status(transactions.get("status")),
                "weeks": _sorted_week_keys(transactions.get("weeks")),
                "errors": dict(transactions.get("errors") or {}),
            },
            "projections": {
                "status": _status(projections.get("status")),
                "season": (
                    str(projections.get("season"))
                    if projections.get("season") is not None
                    else None
                ),
                "week": projections.get("week"),
                "player_count": len(projections.get("players") or {}),
                "error": projections.get("error"),
            },
        },
        "nflverse": nflverse,
        "rankings": {
            "status": "READY" if rankings_ready else "UNAVAILABLE",
            "authority": "Ironbound_power_ranks",
            "schema_version": external.schema_version,
            "ranking_week": metadata.get("ranking_week"),
            "results_through_week": metadata.get("results_through_week"),
            "source_revision": metadata.get("source_revision"),
            "source_metadata": metadata,
        },
        "publication_assets": assets,
        "beat_news": {
            "status": beat_status,
            "blocking": beat_blocking,
            "durable_since": beat_coverage.get("durable_since"),
            "complete_for_reporting_window": beat_coverage.get(
                "complete_for_reporting_window"
            ),
            "source_revision": beat.get("source_revision"),
            "reporting_window": beat.get("reporting_window"),
        },
        "health": {
            "status": _status(
                (dossier.get("roster_health") or {}).get("status")
                if isinstance(dossier.get("roster_health"), dict)
                else "available"
            ),
            "information_cutoff": cutoff_iso,
        },
        "warnings": warnings,
    }
