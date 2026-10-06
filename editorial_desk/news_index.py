"""Build bounded, player-addressable links between accepted news and weekly facts."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from pathlib import Path
from typing import Any


MATERIAL_NEGATIVE_DELTA = -5.0
MAX_STATUS_DISTANCE = timedelta(hours=72)


def build_news_index(
    beat_report: dict[str, Any] | None,
    dossier: dict[str, Any] | None,
    *,
    status_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a compact story index plus auditable context candidates.

    Links are evidence associations only. They never assert that a story caused
    a status change or a below-projection result.
    """
    report = beat_report or {}
    items = [dict(item) for item in report.get("items") or [] if item.get("event_id")]
    by_player: dict[str, list[str]] = {}
    for item in items:
        event_id = str(item["event_id"])
        for player in item.get("league_players") or []:
            player_id = str(player.get("sleeper_player_id") or "")
            if player_id:
                by_player.setdefault(player_id, [])
                if event_id not in by_player[player_id]:
                    by_player[player_id].append(event_id)

    links: list[dict[str, Any]] = []
    links.extend(_status_links(items, status_events or []))
    links.extend(_under_expected_links(items, (dossier or {}).get("game_timing") or {}))
    links.extend(_usage_links(items, (dossier or {}).get("game_timing") or {}))
    links.sort(key=lambda row: (str(row.get("player_id")), str(row.get("event_id")), str(row.get("link_type"))))
    return {
        "schema_version": 1,
        "status": "READY" if report.get("status") == "READY" else str(report.get("status") or "UNAVAILABLE"),
        "source_revision": report.get("source_revision"),
        "reporting_window": report.get("reporting_window"),
        "stories": items,
        "by_player": {key: sorted(value) for key, value in sorted(by_player.items())},
        "links": links,
        "policy": {
            "causal_claims": False,
            "material_negative_projection_delta": MATERIAL_NEGATIVE_DELTA,
            "status_link_window_hours": int(MAX_STATUS_DISTANCE.total_seconds() / 3600),
            "note": "Links identify adjacent evidence for editorial review; timing does not prove causation.",
        },
    }


def build_consumption_receipt(
    beat_report: dict[str, Any] | None,
    packet_path: Path,
    *,
    issue_key: str,
    consumed_at: datetime | None = None,
) -> dict[str, Any]:
    """Create the acknowledgement used by the poster's safe rotation guard."""
    manifest = (beat_report or {}).get("ledger_manifest") or {}
    packet_hash = hashlib.sha256(Path(packet_path).read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "issue_key": str(issue_key),
        "week_key": manifest.get("week_key"),
        "event_count": manifest.get("event_count"),
        "events_sha256": manifest.get("events_sha256"),
        "source_revision": (beat_report or {}).get("source_revision"),
        "packet_sha256": packet_hash,
        "consumed_at": (consumed_at or datetime.now().astimezone()).isoformat(),
        "policy": "Rotate the active news inbox only after this exact revision is persisted in the publication packet.",
    }


def _status_links(items: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("event_type") or "") != "PLAYER_STATUS_CHANGE":
            continue
        entity = event.get("entities") or {}
        player_id = str(entity.get("player_id") or "")
        observed = _parse_time(event.get("observed_at"))
        if not player_id or observed is None:
            continue
        for item in items:
            player = _player(item, player_id)
            published = _parse_time(item.get("published_at"))
            if player is None or published is None:
                continue
            distance = abs(observed - published)
            if distance > MAX_STATUS_DISTANCE:
                continue
            health = bool((item.get("editorial_lanes") or {}).get("health_context"))
            result.append({
                "link_type": "sleeper_status_context",
                "event_id": item["event_id"],
                "player_id": player_id,
                "relationship": player.get("role"),
                "status_event_id": event.get("event_id"),
                "status_before": entity.get("status_before"),
                "status_after": entity.get("status_after"),
                "story_published_at": item.get("published_at"),
                "status_observed_at": event.get("observed_at"),
                "temporal_relation": "near_status_observation",
                "match_quality": "health_tag_and_temporal" if health else "temporal_only",
                "causal_claim": False,
            })
    return result


def _under_expected_links(items: list[dict[str, Any]], timing: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in timing.get("starter_game_days") or []:
        player_id = str(row.get("player_id") or "")
        projected = _number(row.get("projected_points"))
        actual = _number(row.get("fantasy_points"))
        delta = _number(row.get("projection_difference"))
        if not player_id or projected is None or actual is None or delta is None or not row.get("game_complete"):
            continue
        if not (delta <= MATERIAL_NEGATIVE_DELTA or (projected >= 8 and delta <= projected * -0.25)):
            continue
        game_date = str(row.get("gameday") or "")
        for item in items:
            player = _player(item, player_id)
            published = str(item.get("published_at") or "")
            if player is None or not game_date or not published or published[:10] > game_date:
                continue
            result.append({
                "link_type": "under_expected_context",
                "event_id": item["event_id"],
                "player_id": player_id,
                "relationship": player.get("role"),
                "story_published_at": published,
                "game_date": game_date,
                "actual_points": actual,
                "projected_points": projected,
                "projection_difference": delta,
                "temporal_relation": "story_on_or_before_game_date",
                "match_quality": "pregame_story_and_material_negative_delta",
                "causal_claim": False,
            })
    return result


def _usage_links(items: list[dict[str, Any]], timing: dict[str, Any]) -> list[dict[str, Any]]:
    players = {str(row.get("player_id")) for row in timing.get("starter_game_days") or [] if row.get("player_id")}
    result: list[dict[str, Any]] = []
    for item in items:
        if not (item.get("editorial_lanes") or {}).get("usage_context"):
            continue
        for player in item.get("league_players") or []:
            player_id = str(player.get("sleeper_player_id") or "")
            if player_id in players:
                result.append({
                    "link_type": "usage_context",
                    "event_id": item["event_id"],
                    "player_id": player_id,
                    "relationship": player.get("role"),
                    "match_quality": "usage_lane_and_starter_game",
                    "causal_claim": False,
                })
    return result


def _player(item: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    return next(
        (row for row in item.get("league_players") or [] if str(row.get("sleeper_player_id") or "") == player_id),
        None,
    )


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
